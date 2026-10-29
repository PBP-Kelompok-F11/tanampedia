from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.test import Client
from django.urls import reverse

from .forms import QuestionForm
from .models import AnswerOption, DailyChallenge, Question, QuizAttempt


class QuizModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='quiz-user')
        cls.other_user = get_user_model().objects.create_user(username='other-quiz-user')
        cls.question = Question.objects.create(
            prompt='Bagaimana menjaga tanaman tetap sehat?',
            explanation='Perawatan disesuaikan dengan kebutuhan tanaman.',
            created_by=cls.user,
        )
        cls.options = [
            AnswerOption.objects.create(
                question=cls.question, position=position,
                text=f'Pilihan {position}', is_correct=position == 1,
            )
            for position in range(1, 5)
        ]
        cls.challenge = DailyChallenge.objects.create(date=date(2026, 1, 1), question=cls.question)

    def test_complete_question_can_be_scheduled(self):
        self.challenge.full_clean()
        self.question.validate_options()
        self.assertEqual(list(self.question.options.all()), self.options)

    def test_incomplete_question_cannot_be_scheduled(self):
        for count in range(4):
            with self.subTest(option_count=count):
                question = Question.objects.create(prompt='Draft', explanation='Penjelasan')
                for position in range(1, count + 1):
                    AnswerOption.objects.create(question=question, position=position, text='Pilihan')
                challenge = DailyChallenge(date=date(2026, 2, 1), question=question)
                with self.assertRaisesMessage(ValidationError, 'tepat empat'):
                    challenge.full_clean()

    def test_unsaved_question_is_not_ready(self):
        with self.assertRaisesMessage(ValidationError, 'tepat empat'):
            Question(prompt='Draft', explanation='Penjelasan').validate_options()

    def test_question_without_correct_answer_cannot_be_scheduled(self):
        self.question.options.update(is_correct=False)
        with self.assertRaisesMessage(ValidationError, 'tepat satu jawaban benar'):
            self.challenge.full_clean()

    def test_inactive_question_cannot_be_scheduled(self):
        self.question.is_active = False
        self.question.save(update_fields=['is_active'])
        with self.assertRaisesMessage(ValidationError, 'masih aktif'):
            self.challenge.full_clean()

    def test_database_rejects_duplicate_option_position(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AnswerOption.objects.create(question=self.question, position=1, text='Duplikat')

    def test_database_rejects_position_outside_four_choices(self):
        for position in [0, 5]:
            with self.subTest(position=position):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    AnswerOption.objects.create(question=self.question, position=position, text='Invalid')

    def test_database_rejects_second_correct_answer(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AnswerOption.objects.filter(pk=self.options[1].pk).update(is_correct=True)

    def test_database_rejects_two_challenges_on_same_date(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            DailyChallenge.objects.create(date=self.challenge.date, question=self.question)

    def test_question_can_be_reused_on_another_date(self):
        other = DailyChallenge.objects.create(
            date=self.challenge.date + timedelta(days=1), question=self.question,
        )
        other.full_clean()

    def test_database_rejects_second_attempt_for_same_user_and_challenge(self):
        QuizAttempt.objects.create(
            user=self.user, challenge=self.challenge,
            selected_option=self.options[0], is_correct=True, points_awarded=10,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            QuizAttempt.objects.create(
                user=self.user, challenge=self.challenge,
                selected_option=self.options[1], is_correct=False,
            )

    def test_different_users_can_answer_same_challenge(self):
        for user in [self.user, self.other_user]:
            QuizAttempt.objects.create(
                user=user, challenge=self.challenge,
                selected_option=self.options[0], is_correct=True,
            )
        self.assertEqual(self.challenge.attempts.count(), 2)

    def test_same_user_can_answer_on_different_dates(self):
        other = DailyChallenge.objects.create(
            date=self.challenge.date + timedelta(days=1), question=self.question,
        )
        for challenge in [self.challenge, other]:
            QuizAttempt.objects.create(
                user=self.user, challenge=challenge,
                selected_option=self.options[0], is_correct=True,
            )
        self.assertEqual(self.user.quiz_attempts.count(), 2)

    def test_option_must_belong_to_challenge_question(self):
        other_question = Question.objects.create(prompt='Soal lain', explanation='Penjelasan')
        other_option = AnswerOption.objects.create(
            question=other_question, position=1, text='Jawaban lain', is_correct=True,
        )
        attempt = QuizAttempt(
            user=self.user, challenge=self.challenge, selected_option=other_option, is_correct=True,
        )
        with self.assertRaisesMessage(ValidationError, 'bukan milik soal'):
            attempt.full_clean()

    def test_result_must_match_selected_option(self):
        attempt = QuizAttempt(
            user=self.user, challenge=self.challenge,
            selected_option=self.options[0], is_correct=False,
        )
        with self.assertRaisesMessage(ValidationError, 'Hasil harus sesuai'):
            attempt.full_clean()

    def test_database_rejects_points_for_wrong_answer(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            QuizAttempt.objects.create(
                user=self.user, challenge=self.challenge,
                selected_option=self.options[1], is_correct=False, points_awarded=10,
            )

    def test_attempt_preserves_snapshot_when_question_is_deleted(self):
        attempt = QuizAttempt.objects.create(
            user=self.user, challenge=self.challenge,
            selected_option=self.options[0], is_correct=True, points_awarded=10,
        )
        attempt.full_clean()
        self.assertIsNotNone(attempt.answered_at)
        snapshot = attempt.question_snapshot
        with self.assertRaises(ProtectedError):
            self.challenge.delete()
        self.question.delete()
        attempt.refresh_from_db()
        self.challenge.refresh_from_db()
        self.assertIsNone(attempt.selected_option_id)
        self.assertIsNone(self.challenge.question_id)
        self.assertEqual(attempt.question_snapshot, snapshot)
        attempt.full_clean()


def question_data(**updates):
    data = {
        'prompt': 'Apa yang dibutuhkan tanaman?',
        'explanation': 'Penjelasan rahasia untuk setelah menjawab.',
        'option_1': 'Cahaya yang sesuai',
        'option_2': 'Air tanpa batas',
        'option_3': 'Tanah selalu kering',
        'option_4': 'Tidak perlu perawatan',
        'correct_position': '1',
        'is_active': 'on',
    }
    data.update(updates)
    return data


def create_bank_question(prompt='Soal dari bank soal', active=True):
    question = Question.objects.create(
        prompt=prompt, explanation='Penjelasan rahasia bank soal.', is_active=active,
    )
    for position in range(1, 5):
        AnswerOption.objects.create(
            question=question, position=position,
            text=f'Pilihan {position}', is_correct=position == 1,
        )
    return question


class QuestionFormTests(TestCase):
    def test_saves_four_options_and_exactly_one_correct_answer(self):
        form = QuestionForm(data=question_data(correct_position='3'))
        self.assertTrue(form.is_valid(), form.errors)
        question = form.save()
        question.validate_options()
        self.assertEqual(question.options.get(is_correct=True).position, 3)
        self.assertEqual(question.options.count(), 4)

    def test_required_fields_and_invalid_answer_key(self):
        for field in ['prompt', 'explanation', 'option_1', 'option_2', 'option_3', 'option_4', 'correct_position']:
            with self.subTest(field=field):
                form = QuestionForm(data=question_data(**{field: '   '}))
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
        for invalid in ['0', '5', 'A']:
            with self.subTest(key=invalid):
                form = QuestionForm(data=question_data(correct_position=invalid))
                self.assertFalse(form.is_valid())
                self.assertIn('correct_position', form.errors)

    def test_duplicate_choices_ignore_case_and_surrounding_spaces(self):
        form = QuestionForm(data=question_data(option_2='  CAHAYA YANG SESUAI  '))
        self.assertFalse(form.is_valid())
        self.assertIn('Keempat pilihan jawaban harus berbeda.', form.non_field_errors())

    def test_rejects_choice_longer_than_500_characters(self):
        form = QuestionForm(data=question_data(option_1='x' * 501))
        self.assertFalse(form.is_valid())
        self.assertIn('option_1', form.errors)

    def test_edit_moves_answer_key_without_replacing_option_ids(self):
        question = create_bank_question()
        original_ids = list(question.options.values_list('id', flat=True))
        form = QuestionForm(data=question_data(correct_position='4'), instance=question)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(list(question.options.values_list('id', flat=True)), original_ids)
        self.assertEqual(question.options.get(is_correct=True).position, 4)

    def test_prefills_options_and_key(self):
        question = create_bank_question()
        form = QuestionForm(instance=question)
        self.assertEqual(form.initial['option_1'], 'Pilihan 1')
        self.assertEqual(form.initial['correct_position'], 1)

    def test_used_question_allows_all_content_and_status_changes(self):
        question = create_bank_question()
        DailyChallenge.objects.create(date=date(2026, 1, 1), question=question)
        form = QuestionForm(data=question_data(is_active='', correct_position='4'), instance=question)
        self.assertFalse(any(field.disabled for field in form.fields.values()))
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        question.refresh_from_db()
        self.assertFalse(question.is_active)
        self.assertEqual(question.prompt, question_data()['prompt'])
        self.assertEqual(question.explanation, question_data()['explanation'])
        self.assertEqual(question.options.get(is_correct=True).position, 4)

    def test_new_history_after_form_validation_still_allows_editing(self):
        question = create_bank_question()
        form = QuestionForm(data=question_data(), instance=question)
        self.assertTrue(form.is_valid(), form.errors)
        DailyChallenge.objects.create(date=date(2026, 1, 1), question=question)
        form.save()
        question.refresh_from_db()
        self.assertEqual(question.prompt, question_data()['prompt'])

    def test_deleted_question_cannot_be_recreated_from_stale_form(self):
        question = create_bank_question()
        form = QuestionForm(data=question_data(), instance=question)
        self.assertTrue(form.is_valid(), form.errors)
        Question.objects.filter(pk=question.pk).delete()
        with self.assertRaisesMessage(ValidationError, 'sudah dihapus'):
            form.save()
        self.assertFalse(Question.objects.exists())

    def test_failure_saving_options_rolls_back_entire_new_question(self):
        from unittest.mock import patch

        form = QuestionForm(data=question_data())
        self.assertTrue(form.is_valid())
        with patch('quiz.forms.AnswerOption.objects.update_or_create', side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                form.save()
        self.assertFalse(Question.objects.exists())
        self.assertFalse(AnswerOption.objects.exists())


class QuestionManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username='quiz-admin', email='quiz-admin@example.com', password='test-password',
        )
        cls.user = get_user_model().objects.create_user(username='quiz-viewer')
        cls.staff = get_user_model().objects.create_user(username='quiz-staff', is_staff=True)
        cls.question = create_bank_question()

    def management_urls(self):
        return [
            reverse('quiz:question_list'), reverse('quiz:question_create'),
            reverse('quiz:question_update', args=[self.question.pk]),
            reverse('quiz:question_delete', args=[self.question.pk]),
        ]

    def test_anonymous_is_redirected_to_login_on_every_management_endpoint(self):
        for url in self.management_urls():
            for method in ['get', 'post']:
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url)
                    self.assertEqual(response.status_code, 302)
                    self.assertTrue(response.url.startswith(reverse('accounts:login') + '?next='))
        self.assertEqual(Question.objects.count(), 1)

    def test_regular_users_and_staff_are_denied_on_every_management_endpoint(self):
        for user in [self.user, self.staff]:
            self.client.force_login(user)
            for url in self.management_urls():
                for method in ['get', 'post']:
                    with self.subTest(user=user.username, url=url, method=method):
                        self.assertEqual(getattr(self.client, method)(url).status_code, 403)
        self.assertEqual(Question.objects.count(), 1)

    def test_only_superusers_see_management_links(self):
        url = reverse('quiz:today')
        self.assertNotContains(self.client.get(url), 'Tambah Soal Kuis')
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(url), 'Tambah Soal Kuis')
        self.client.force_login(self.admin)
        response = self.client.get(url)
        self.assertContains(response, 'Tambah Soal Kuis')
        self.assertContains(response, reverse('quiz:question_list'))

    def test_superuser_can_render_all_management_pages(self):
        self.client.force_login(self.admin)
        for url in self.management_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_create_sets_author_from_session_and_saves_options(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('quiz:question_create'), question_data(created_by=str(self.user.pk)),
        )
        self.assertRedirects(response, reverse('quiz:question_list'))
        question = Question.objects.exclude(pk=self.question.pk).get()
        self.assertEqual(question.created_by, self.admin)
        question.validate_options()

    def test_invalid_form_keeps_values_and_creates_nothing(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('quiz:question_create'), question_data(option_2=''))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cahaya yang sesuai')
        self.assertIn('option_2', response.context['form'].errors)
        self.assertEqual(Question.objects.count(), 1)
        self.assertEqual(AnswerOption.objects.count(), 4)

    def test_edit_updates_question_and_answer_key(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('quiz:question_update', args=[self.question.pk]),
            question_data(correct_position='2'),
        )
        self.assertRedirects(response, reverse('quiz:question_list'))
        self.question.refresh_from_db()
        self.assertEqual(self.question.prompt, question_data()['prompt'])
        self.assertEqual(self.question.options.get(is_correct=True).position, 2)

    def test_delete_get_is_confirmation_only_and_post_removes_options(self):
        self.client.force_login(self.admin)
        url = reverse('quiz:question_delete', args=[self.question.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Question.objects.filter(pk=self.question.pk).exists())
        response = self.client.post(url)
        self.assertRedirects(response, reverse('quiz:question_list'))
        self.assertFalse(Question.objects.exists())
        self.assertFalse(AnswerOption.objects.exists())

    def test_can_delete_scheduled_question_and_preserve_schedule(self):
        challenge = DailyChallenge.objects.create(date=date(2026, 1, 1), question=self.question)
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('quiz:question_delete', args=[self.question.pk]), follow=True,
        )
        self.assertContains(response, 'berhasil dihapus')
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())
        challenge.refresh_from_db()
        self.assertIsNone(challenge.question_id)

    def test_missing_questions_return_404(self):
        self.client.force_login(self.admin)
        for name in ['quiz:question_update', 'quiz:question_delete']:
            self.assertEqual(self.client.get(reverse(name, args=[999999])).status_code, 404)

    def test_post_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(reverse('quiz:question_create'), question_data()).status_code, 403)
        csrf_client.get(reverse('quiz:question_create'))
        data = question_data(csrfmiddlewaretoken=csrf_client.cookies['csrftoken'].value)
        self.assertEqual(csrf_client.post(reverse('quiz:question_create'), data).status_code, 302)

    def test_management_pages_escape_user_text(self):
        self.question.prompt = '<script>alert("question")</script>'
        self.question.save(update_fields=['prompt'])
        self.client.force_login(self.admin)
        response = self.client.get(reverse('quiz:question_list'))
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, self.question.prompt)


class RandomQuizPageTests(TestCase):
    def test_empty_bank_shows_empty_state(self):
        response = self.client.get(reverse('quiz:today'))
        self.assertContains(response, 'Belum ada soal kuis yang ditambahkan.')
        self.assertIsNone(response.context['question'])

    def test_inactive_incomplete_and_keyless_questions_are_not_selected(self):
        create_bank_question(active=False)
        incomplete = create_bank_question()
        incomplete.options.last().delete()
        keyless = create_bank_question()
        keyless.options.update(is_correct=False)
        response = self.client.get(reverse('quiz:today'))
        self.assertIsNone(response.context['question'])

    def test_one_question_can_reappear_on_refresh(self):
        question = create_bank_question()
        for _ in range(3):
            response = self.client.get(reverse('quiz:today'))
            self.assertEqual(response.context['question'].pk, question.pk)
            self.assertContains(response, question.prompt)
        self.assertEqual(dict(self.client.session), {})

    def test_selected_question_is_from_valid_active_bank(self):
        choices = [create_bank_question(prompt=f'Valid {index}') for index in range(3)]
        create_bank_question(active=False)
        for _ in range(5):
            response = self.client.get(reverse('quiz:today'))
            self.assertIn(response.context['question'].pk, [question.pk for question in choices])

    def test_page_does_not_leak_explanation_or_key(self):
        question = create_bank_question()
        response = self.client.get(reverse('quiz:today'))
        self.assertNotContains(response, question.explanation)
        self.assertNotContains(response, 'Jawaban benar')
        self.assertContains(response, ' disabled class=', count=4)
        self.assertEqual(QuizAttempt.objects.count(), 0)

    def test_random_page_is_not_cached_and_escapes_question_content(self):
        question = create_bank_question(prompt='<script>alert("question")</script>')
        response = self.client.get(reverse('quiz:today'))
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, question.prompt)
