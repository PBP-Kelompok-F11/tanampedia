from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

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

    def test_attempt_preserves_challenge_and_selected_option(self):
        attempt = QuizAttempt.objects.create(
            user=self.user, challenge=self.challenge,
            selected_option=self.options[0], is_correct=True, points_awarded=10,
        )
        attempt.full_clean()
        self.assertIsNotNone(attempt.answered_at)
        for referenced in [self.question, self.challenge, self.options[0]]:
            with self.subTest(model=type(referenced).__name__):
                with self.assertRaises(ProtectedError):
                    referenced.delete()
