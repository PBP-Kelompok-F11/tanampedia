from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from .models import QuizAttempt
from .services import answer_token, next_reset, quiz_date
from .tests import create_bank_question


class QuizAnswerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='answer-user')
        cls.other = get_user_model().objects.create_user(username='answer-other')
        cls.question = create_bank_question()
        cls.correct = cls.question.options.get(is_correct=True)
        cls.wrong = cls.question.options.get(position=2)

    def setUp(self):
        self.client.force_login(self.user)
        self.today = reverse('quiz:today')
        self.answer = reverse('quiz:answer')

    def token(self):
        return self.client.get(self.today).context['answer_token']

    def submit(self, option=None, token=None, **extra):
        return self.client.post(self.answer, {
            'answer_token': token or self.token(),
            'option': (option or self.correct).pk, **extra,
        })

    def points(self):
        return Profile.objects.get(user=self.user).pedia_points

    def test_correct_answer_awards_points_and_locks_until_midnight(self):
        token = self.token()
        original_add_points = Profile.add_points
        with patch.object(Profile, 'add_points', autospec=True, side_effect=original_add_points) as add:
            response = self.submit(token=token)
            add.assert_called_once()
            self.assertEqual(add.call_args.args[1], 10)
        self.assertRedirects(response, self.today, fetch_redirect_response=False)
        self.assertEqual(self.points(), 10)
        result = self.client.get(self.today)
        self.assertTrue(result.context['cooldown'])
        self.assertContains(result, 'Jawaban benar! +10 PediaPoints.')
        self.assertContains(result, 'border-primary-500 bg-primary-100 text-primary-700')
        self.assertContains(result, self.question.explanation)
        self.assertContains(result, '00.00 WIB')
        self.assertIsNone(result.context['answer_token'])

    def test_real_add_points_preserves_previous_balance(self):
        Profile.objects.filter(user=self.user).update(pedia_points=25)
        self.submit()
        self.assertEqual(self.points(), 35)

    def test_wrong_answer_shows_red_explanation_and_refresh_allows_retry(self):
        self.submit(option=self.wrong)
        result = self.client.get(self.today)
        self.assertFalse(result.context['cooldown'])
        self.assertContains(result, 'border-red-500 bg-red-50 text-red-700')
        self.assertContains(result, self.question.explanation)
        self.assertEqual(self.points(), 0)
        refreshed = self.client.get(self.today)
        self.assertIsNone(refreshed.context['result'])
        self.assertTrue(refreshed.context['answer_token'])
        self.assertEqual(refreshed.context['question'].pk, self.question.pk)
        self.submit(token=refreshed.context['answer_token'])
        self.assertEqual(self.points(), 10)
        self.assertEqual(QuizAttempt.objects.count(), 2)

    def test_replayed_submission_cannot_change_answer_or_award_again(self):
        token = self.token()
        self.submit(option=self.wrong, token=token)
        self.submit(token=token)
        self.assertEqual(self.points(), 0)
        self.assertEqual(QuizAttempt.objects.count(), 1)
        self.assertFalse(QuizAttempt.objects.get().is_correct)

    def test_two_tabs_and_duplicate_clicks_only_award_once(self):
        first, second = self.token(), self.token()
        self.submit(token=first)
        self.submit(token=first)
        self.submit(token=second)
        self.assertEqual(self.points(), 10)
        self.assertEqual(QuizAttempt.objects.count(), 1)

    def test_token_is_bound_to_logged_in_user(self):
        token = self.token()
        self.client.force_login(self.other)
        self.submit(token=token)
        self.assertFalse(QuizAttempt.objects.exists())

    def test_missing_tampered_and_invalid_options_do_not_write(self):
        token = self.token()
        for data in [{}, {'answer_token': token + 'x', 'option': self.correct.pk},
                     {'answer_token': token, 'option': 'not-an-id'},
                     {'answer_token': token, 'option': '999999'}]:
            with self.subTest(data=data):
                self.assertEqual(self.client.post(self.answer, data).status_code, 302)
                self.assertFalse(QuizAttempt.objects.exists())
        self.assertEqual(self.points(), 0)

    def test_cannot_answer_option_from_another_question(self):
        other_question = create_bank_question(prompt='Other')
        self.submit(option=other_question.options.first(), token=answer_token(self.question, self.user, quiz_date()))
        self.assertFalse(QuizAttempt.objects.exists())

    def test_inactive_deleted_or_edited_question_rejects_old_form(self):
        for change in ['edit', 'inactive', 'delete']:
            question = create_bank_question(prompt=change)
            token = answer_token(question, self.user, quiz_date())
            option_id = question.options.first().pk
            if change == 'delete':
                question.delete()
            elif change == 'inactive':
                question.is_active = False
                question.save()
            else:
                question.prompt = 'Changed'
                question.save()
            self.client.post(self.answer, {'answer_token': token, 'option': option_id})
            self.assertFalse(QuizAttempt.objects.exists())

    def test_server_ignores_posted_points_correctness_date_and_user(self):
        self.submit(option=self.wrong, points_awarded=1000, is_correct=True,
                    quiz_date='2099-01-01', user=self.other.pk)
        attempt = QuizAttempt.objects.get()
        self.assertEqual(attempt.user, self.user)
        self.assertEqual(attempt.quiz_date, quiz_date())
        self.assertEqual(attempt.points_awarded, 0)
        self.assertFalse(attempt.is_correct)

    @override_settings(QUIZ_CORRECT_ANSWER_POINTS=17)
    def test_reward_can_be_configured(self):
        self.assertContains(self.client.get(self.today), '+17 PediaPoints')
        self.submit()
        self.assertEqual(self.points(), 17)
        self.assertEqual(QuizAttempt.objects.get().points_awarded, 17)

    def test_points_failure_rolls_back_attempt_and_reward(self):
        token = self.token()
        with patch('accounts.models.Profile.add_points', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):
                self.submit(token=token)
        self.assertFalse(QuizAttempt.objects.exists())
        self.assertEqual(self.points(), 0)
        self.submit(token=token)
        self.assertEqual(self.points(), 10)

    def test_sqlite_write_contention_can_be_retried_without_losing_chance(self):
        if connection.vendor != 'sqlite':
            self.skipTest('SQLite-specific write contention')
        token = self.token()
        with patch('quiz.views.process_answer', side_effect=OperationalError('database is locked')):
            response = self.submit(token=token)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(QuizAttempt.objects.exists())
        self.assertEqual(self.points(), 0)
        self.submit(token=token)
        self.assertEqual(self.points(), 10)

    def test_database_rejects_second_success_for_same_day(self):
        self.submit()
        with self.assertRaises(IntegrityError), transaction.atomic():
            QuizAttempt.objects.create(user=self.user, quiz_date=quiz_date(),
                                       selected_option=self.correct, is_correct=True, points_awarded=10)

    def test_anonymous_cannot_submit_and_get_cannot_mutate(self):
        self.assertEqual(self.client.get(self.answer).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post(self.answer).status_code, 302)
        self.assertFalse(QuizAttempt.objects.exists())

    def test_answer_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.get(self.today)
        data = {'answer_token': response.context['answer_token'], 'option': self.correct.pk}
        self.assertEqual(client.post(self.answer, data).status_code, 403)
        data['csrfmiddlewaretoken'] = client.cookies['csrftoken'].value
        self.assertEqual(client.post(self.answer, data).status_code, 302)
        self.assertEqual(self.points(), 10)

    def test_wib_date_and_new_day_unlock_independent_of_global_timezone(self):
        before = datetime(2026, 10, 26, 16, 59, tzinfo=dt_timezone.utc)
        after = datetime(2026, 10, 26, 17, 0, tzinfo=dt_timezone.utc)
        with patch('quiz.services.timezone.now', return_value=before):
            self.assertEqual(quiz_date(), date(2026, 10, 26))
            token = self.token()
            self.submit(token=token)
            self.assertTrue(self.client.get(self.today).context['cooldown'])
        with patch('quiz.services.timezone.now', return_value=after):
            self.assertEqual(quiz_date(), date(2026, 10, 27))
            response = self.client.get(self.today)
            self.assertFalse(response.context['cooldown'])
            self.assertEqual(response.context['reset_date'], date(2026, 10, 28))
            self.submit(token=token)  # Yesterday's form must be rejected.
            self.assertEqual(self.points(), 10)
            self.submit(token=response.context['answer_token'])
            self.assertEqual(self.points(), 20)

    def test_reset_is_next_midnight_in_jakarta(self):
        reset = next_reset(date(2026, 12, 31))
        self.assertEqual(reset.isoformat(), '2027-01-01T00:00:00+07:00')

    def test_attempt_history_locks_question_and_cannot_be_deleted(self):
        from .forms import QuestionForm
        from django.db.models.deletion import ProtectedError

        self.submit(option=self.wrong)
        self.assertTrue(QuestionForm(instance=self.question).is_locked)
        with self.assertRaises(ProtectedError):
            self.question.delete()


class QuizRewardMigrationTests(TransactionTestCase):
    def test_existing_attempts_keep_their_challenge_date_and_reward(self):
        executor = MigrationExecutor(connection)
        old = [('quiz', '0001_initial')]
        new = [('quiz', '0002_daily_answer_rewards')]
        executor.migrate(old)
        try:
            apps = executor.loader.project_state(old).apps
            user = apps.get_model('auth', 'User').objects.create(username='legacy-answer')
            question = apps.get_model('quiz', 'Question').objects.create(prompt='Legacy', explanation='Legacy')
            option = apps.get_model('quiz', 'AnswerOption').objects.create(
                question=question, position=1, text='Legacy answer', is_correct=True,
            )
            challenge = apps.get_model('quiz', 'DailyChallenge').objects.create(
                question=question, date=date(2026, 1, 1),
            )
            attempt = apps.get_model('quiz', 'QuizAttempt').objects.create(
                user=user, challenge=challenge, selected_option=option,
                is_correct=True, points_awarded=10,
            )
        finally:
            MigrationExecutor(connection).migrate(new)
        migrated = QuizAttempt.objects.get(pk=attempt.pk)
        self.assertEqual(migrated.quiz_date, date(2026, 1, 1))
        self.assertEqual(migrated.challenge_id, challenge.pk)
        self.assertEqual(migrated.points_awarded, 10)
        self.assertIsNone(migrated.submission_id)
