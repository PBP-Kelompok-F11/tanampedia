from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError, connection
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Profile
from .models import QuizAttempt
from .tests import create_bank_question


class QuizFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='quiz-flow-user')
        cls.question = create_bank_question()

    def setUp(self):
        self.client.force_login(self.user)
        self.today = reverse('quiz:today')
        self.answer = reverse('quiz:answer')

    def submit_json(self, page, position=1):
        return self.client.post(self.answer, {
            'answer_token': page.context['answer_token'],
            'option': page.context['question'].options.get(position=position).pk,
        }, HTTP_ACCEPT='application/json')

    def test_home_to_correct_answer_and_profile_balance(self):
        home = self.client.get(reverse('main:home'))
        self.assertContains(home, f'href="{self.today}"', count=2)
        page = self.client.get(self.today)
        self.assertContains(page, '/static/js/quiz/answer_feedback.js')
        response = self.submit_json(page)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        html = response.json()['html']
        self.assertIn('border-primary-500 bg-primary-100 text-primary-700', html)
        self.assertIn(self.question.explanation, html)
        self.assertIn('Reward PediaPoints hari ini sudah diterima.', html)
        self.assertIn('data-quiz-result', html)
        self.assertNotIn('Coba Lagi', html)
        profile = self.client.get(reverse('accounts:profile'))
        self.assertEqual(profile.context['profile'].pedia_points, 10)
        refreshed = self.client.get(self.today)
        self.assertTrue(refreshed.context['cooldown'])
        self.assertContains(refreshed, 'Jawaban benar! +10 PediaPoints.')

    def test_wrong_feedback_refresh_and_retry_without_extra_feedback_page(self):
        page = self.client.get(self.today)
        response = self.submit_json(page, position=2)
        self.assertEqual(response.status_code, 200)
        html = response.json()['html']
        self.assertIn('border-red-500 bg-red-50 text-red-700', html)
        self.assertIn('Coba Lagi', html)
        self.assertIn(self.question.explanation, html)
        self.assertNotIn('quiz_result_id', self.client.session)
        retry = self.client.get(self.today)
        self.assertTrue(retry.context['answer_token'])
        self.assertIsNone(retry.context['result'])
        self.assertEqual(self.submit_json(retry).status_code, 200)
        self.assertEqual(Profile.objects.get(user=self.user).pedia_points, 10)
        self.assertEqual(QuizAttempt.objects.count(), 2)

    def test_json_replay_does_not_award_twice(self):
        page = self.client.get(self.today)
        first = self.submit_json(page)
        second = self.submit_json(page)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertIn('Jawaban benar! +10 PediaPoints.', second.json()['html'])
        self.assertEqual(QuizAttempt.objects.count(), 1)
        self.assertEqual(Profile.objects.get(user=self.user).pedia_points, 10)

    def test_second_tab_receives_actual_result_question(self):
        page = self.client.get(self.today)
        self.submit_json(page)
        second = create_bank_question(prompt='Soal tab kedua')
        from .services import answer_token, quiz_date
        response = self.client.post(self.answer, {
            'answer_token': answer_token(second, self.user, quiz_date()),
            'option': second.options.first().pk,
        }, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.question.prompt, response.json()['html'])
        self.assertNotIn(second.prompt, response.json()['html'])
        self.assertEqual(QuizAttempt.objects.count(), 1)

    def test_invalid_json_answer_returns_error_without_writing(self):
        response = self.client.post(self.answer, {'answer_token': 'invalid', 'option': '1'},
                                    HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
        self.assertNotIn('html', response.json())
        self.assertFalse(QuizAttempt.objects.exists())

    def test_html_feedback_escapes_explanation(self):
        self.question.explanation = '<script>alert("explanation")</script>'
        self.question.save(update_fields=['explanation'])
        response = self.submit_json(self.client.get(self.today))
        html = response.json()['html']
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn(self.question.explanation, html)

    def test_json_still_requires_csrf_and_authentication(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        page = csrf_client.get(self.today)
        data = {'answer_token': page.context['answer_token'], 'option': self.question.options.first().pk}
        self.assertEqual(csrf_client.post(self.answer, data, HTTP_ACCEPT='application/json').status_code, 403)
        data['csrfmiddlewaretoken'] = csrf_client.cookies['csrftoken'].value
        self.assertEqual(csrf_client.post(self.answer, data, HTTP_ACCEPT='application/json').status_code, 200)
        self.client.logout()
        response = self.client.post(self.answer, data, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.json()['login_url'].startswith(reverse('account_login')))
        self.assertIn('next=' + self.today, response.json()['login_url'])
        fallback = self.client.post(self.answer, data)
        self.assertEqual(fallback.status_code, 302)
        self.assertIn('next=' + self.today, fallback.url)

    def test_sqlite_busy_json_response_allows_retry(self):
        if connection.vendor != 'sqlite':
            self.skipTest('SQLite-specific write contention')
        page = self.client.get(self.today)
        with patch('quiz.views.process_answer', side_effect=OperationalError('database is locked')):
            response = self.submit_json(page)
        self.assertEqual(response.status_code, 503)
        self.assertIn('error', response.json())
        self.assertFalse(QuizAttempt.objects.exists())
        self.assertEqual(self.submit_json(page).status_code, 200)
