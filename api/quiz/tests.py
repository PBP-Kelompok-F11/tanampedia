from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Profile
from quiz.services import answer_token, quiz_date
from quiz.tests import create_bank_question

API_TODAY = reverse('quiz_api:today')
API_ANSWER = reverse('quiz_api:answer')


class QuizApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='quiz-api-user')
        cls.question = create_bank_question()

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def get_today(self):
        return self.client.get(API_TODAY, HTTP_ACCEPT='application/json')

    def submit(self, token, option):
        return self.client.post(
            API_ANSWER, {'answer_token': token, 'option': option}, format='json',
        )

    def test_today_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.get(API_TODAY)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.headers['Content-Type'], 'application/json')

    def test_answer_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.post(API_ANSWER, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_today_returns_question_without_leaking_answers(self):
        response = self.get_today()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body['question']['question_id'], self.question.pk)
        self.assertEqual(len(body['question']['options']), 4)
        self.assertNotEqual(body['answer_token'], None)
        self.assertEqual(body['status']['answered'], False)
        self.assertEqual(body['status']['reward_points'], 10)
        payload = response.content.decode()
        self.assertNotIn('is_correct', payload.replace('"answer_token"', ''))
        self.assertNotIn('explanation', payload)
        self.assertNotIn(self.question.explanation, payload)

    def test_today_after_answer_shows_result_not_new_token(self):
        day = quiz_date()
        token = answer_token(self.question, self.user, day)
        self.submit(token, self.question.options.get(position=1).pk)
        response = self.get_today()
        body = response.json()
        self.assertIsNone(body['answer_token'])
        self.assertIsNone(body['question'])
        self.assertEqual(body['result']['is_correct'], True)
        self.assertEqual(body['status']['answered'], True)
        self.assertEqual(body['status']['answered_correctly'], True)

    def test_correct_answer_awards_points(self):
        day = quiz_date()
        token = answer_token(self.question, self.user, day)
        correct = self.question.options.filter(is_correct=True).first().pk
        response = self.submit(token, correct)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body['result']['is_correct'], True)
        self.assertEqual(body['result']['points_awarded'], 10)
        self.assertIn('explanation', body['result'])
        correct_ids = [
            option['id'] for option in body['result']['options'] if option['is_correct']
        ]
        self.assertEqual(correct_ids, [correct])
        self.assertEqual(Profile.objects.get(user=self.user).pedia_points, 10)

    def test_wrong_answer_awards_no_points(self):
        day = quiz_date()
        token = answer_token(self.question, self.user, day)
        wrong = self.question.options.filter(is_correct=False).first().pk
        response = self.submit(token, wrong)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body['result']['is_correct'], False)
        self.assertEqual(body['result']['points_awarded'], 0)
        self.assertEqual(Profile.objects.get(user=self.user).pedia_points, 0)

    def test_answer_requires_fields(self):
        response = self.client.post(API_ANSWER, {'option': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('answer_token', response.json())
        response = self.client.post(
            API_ANSWER, {'answer_token': 'x', 'option': 'bukan'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_token_rejected(self):
        response = self.submit('bukan-token', 1)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.json())

    def test_option_from_other_question_rejected(self):
        other = create_bank_question(prompt='Soal lain')
        day = quiz_date()
        token = answer_token(self.question, self.user, day)
        response = self.submit(token, other.options.get(position=1).pk)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.json())
        self.assertEqual(self.user.quiz_attempts.count(), 0)

    def test_repeated_submission_does_not_duplicate_reward(self):
        day = quiz_date()
        token = answer_token(self.question, self.user, day)
        correct = self.question.options.filter(is_correct=True).first().pk
        first = self.submit(token, correct)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.json()['reward_received'], True)
        second = self.submit(token, correct)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.json()['result']['is_correct'], True)
        self.assertEqual(second.json()['result']['points_awarded'], 10)
        self.assertEqual(Profile.objects.get(user=self.user).pedia_points, 10)
        self.assertEqual(self.user.quiz_attempts.count(), 1)

    def test_retry_after_wrong_answer(self):
        day = quiz_date()
        wrong = self.question.options.filter(is_correct=False).first().pk
        self.assertEqual(
            self.submit(answer_token(self.question, self.user, day), wrong).status_code,
            status.HTTP_200_OK,
        )
        retry_token = self.get_today().json()['answer_token']
        correct = self.question.options.filter(is_correct=True).first().pk
        retry = self.submit(retry_token, correct)
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        self.assertEqual(self.user.quiz_attempts.count(), 2)
        self.assertEqual(Profile.objects.get(user=self.user).pedia_points, 10)

    def test_integrity_conflict_returns_409(self):
        day = quiz_date()
        token = answer_token(self.question, self.user, day)
        correct = self.question.options.filter(is_correct=True).first().pk
        self.submit(token, correct)

        with patch('api.quiz.views.process_answer', side_effect=IntegrityError('duplikat')):
            response = self.submit(token, correct)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('error', response.json())

    def test_today_with_no_eligible_question(self):
        self.question.is_active = False
        self.question.save(update_fields=['is_active'])
        response = self.get_today()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIsNone(body['question'])
        self.assertIsNone(body['answer_token'])
        self.assertEqual(body['status']['answered'], False)

    def test_points_awarded_from_request_is_ignored(self):
        day = quiz_date()
        token = answer_token(self.question, self.user, day)
        wrong = self.question.options.filter(is_correct=False).first().pk
        response = self.client.post(API_ANSWER, {
            'answer_token': token, 'option': wrong, 'is_correct': True, 'points_awarded': 999,
        }, format='json')
        body = response.json()
        self.assertEqual(body['result']['is_correct'], False)
        self.assertEqual(body['result']['points_awarded'], 0)
