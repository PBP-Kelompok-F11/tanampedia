from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Question(models.Model):
    prompt = models.TextField()
    explanation = models.TextField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='quiz_questions_created', null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.prompt

    def validate_options(self):
        """Drafts may be incomplete; scheduling requires four options and one key."""
        if not self.pk or self.options.count() != 4:
            raise ValidationError('Soal harus memiliki tepat empat pilihan jawaban.')
        if self.options.filter(is_correct=True).count() != 1:
            raise ValidationError('Soal harus memiliki tepat satu jawaban benar.')


class AnswerOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    position = models.PositiveSmallIntegerField(choices=[(1, 'A'), (2, 'B'), (3, 'C'), (4, 'D')])
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['position']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(position__gte=1, position__lte=4),
                name='quiz_option_position_1_to_4',
            ),
            models.UniqueConstraint(
                fields=['question', 'position'], name='quiz_unique_option_position',
            ),
            models.UniqueConstraint(
                fields=['question'], condition=models.Q(is_correct=True),
                name='quiz_one_correct_option',
            ),
        ]

    def __str__(self):
        return f'{self.get_position_display()}. {self.text}'


class DailyChallenge(models.Model):
    date = models.DateField(unique=True)
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name='challenges')

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.date}: {self.question}'

    def clean(self):
        super().clean()
        if not self.question_id:
            return
        if not self.question.is_active:
            raise ValidationError({'question': 'Pilih soal yang masih aktif.'})
        try:
            self.question.validate_options()
        except ValidationError as error:
            raise ValidationError({'question': error.messages}) from error


class QuizAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts',
    )
    challenge = models.ForeignKey(
        DailyChallenge, on_delete=models.PROTECT, related_name='attempts', null=True, blank=True,
    )
    quiz_date = models.DateField(null=True, blank=True)
    submission_id = models.UUIDField(unique=True, null=True, blank=True)
    selected_option = models.ForeignKey(AnswerOption, on_delete=models.PROTECT, related_name='attempts')
    is_correct = models.BooleanField()
    points_awarded = models.PositiveIntegerField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'quiz_date'], condition=models.Q(is_correct=True),
                name='quiz_one_success_per_user_day',
            ),
            models.CheckConstraint(
                condition=models.Q(challenge__isnull=False) | models.Q(quiz_date__isnull=False),
                name='quiz_attempt_has_day',
            ),
            models.UniqueConstraint(
                fields=['user', 'challenge'], name='quiz_unique_user_challenge',
            ),
            models.CheckConstraint(
                condition=models.Q(is_correct=True) | models.Q(points_awarded=0),
                name='quiz_wrong_answer_no_points',
            ),
        ]

    def __str__(self):
        return f'{self.user_id} / {self.challenge_id}'

    def save(self, *args, **kwargs):
        if self.quiz_date is None and self.challenge_id:
            self.quiz_date = self.challenge.date
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if not self.selected_option_id:
            return
        if self.challenge_id and self.selected_option.question_id != self.challenge.question_id:
            raise ValidationError({'selected_option': 'Pilihan bukan milik soal challenge ini.'})
        if self.is_correct != self.selected_option.is_correct:
            raise ValidationError({'is_correct': 'Hasil harus sesuai dengan pilihan jawaban.'})
