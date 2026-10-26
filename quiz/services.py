import hashlib
import json
import uuid
from datetime import datetime, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from .models import Question, QuizAttempt, question_snapshot


QUIZ_TIMEZONE = ZoneInfo('Asia/Jakarta')
TOKEN_SALT = 'quiz.answer.v1'


def quiz_date():
    return timezone.localdate(timezone.now(), QUIZ_TIMEZONE)


def next_reset(day):
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=QUIZ_TIMEZONE)


def daily_success(user, day):
    return QuizAttempt.objects.filter(user=user, quiz_date=day, is_correct=True).first()


def result_question(attempt):
    snapshot = attempt.question_snapshot
    return SimpleNamespace(
        pk=snapshot['question_id'], prompt=snapshot['prompt'], explanation=snapshot['explanation'],
        options=[SimpleNamespace(
            pk=option['id'], position=option['position'], text=option['text'],
            get_position_display=chr(64 + option['position']),
        ) for option in snapshot['options']],
    )


def question_version(question):
    content = [question.prompt, question.explanation, list(
        question.options.values_list('pk', 'text', 'is_correct', 'position')
    )]
    return hashlib.sha256(json.dumps(content, ensure_ascii=False).encode()).hexdigest()


def answer_token(question, user, day):
    return signing.dumps({
        'question': question.pk, 'user': user.pk, 'date': day.isoformat(),
        'submission': str(uuid.uuid4()), 'version': question_version(question),
    }, salt=TOKEN_SALT)


@transaction.atomic
def process_answer(user, token, option_id):
    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=86400)
        submission_id = uuid.UUID(data['submission'])
        question_id = int(data['question'])
        option_id = int(option_id)
    except (signing.BadSignature, ValueError, TypeError, KeyError):
        raise ValidationError('Jawaban tidak valid atau kedaluwarsa. Muat ulang halaman kuis.')

    # Serialize submissions by account; the unique success constraint is a second guard.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    day = quiz_date()
    if data['user'] != user.pk or data['date'] != day.isoformat():
        raise ValidationError('Kesempatan ini sudah kedaluwarsa. Muat ulang halaman kuis.')
    existing = QuizAttempt.objects.filter(user=user, submission_id=submission_id).first()
    if existing:
        return existing
    success = daily_success(user, day)
    if success:
        return success
    question = Question.objects.select_for_update().filter(pk=question_id, is_active=True).first()
    if question is None:
        raise ValidationError('Soal sudah tidak tersedia. Muat ulang halaman kuis.')
    question.validate_options()
    if data.get('version') != question_version(question):
        raise ValidationError('Soal telah diperbarui. Muat ulang halaman kuis.')
    option = question.options.filter(pk=option_id).first()
    if option is None:
        raise ValidationError('Pilih salah satu jawaban dari soal yang ditampilkan.')
    points = settings.QUIZ_CORRECT_ANSWER_POINTS if option.is_correct else 0
    attempt = QuizAttempt.objects.create(
        user=user, selected_option=option, quiz_date=day,
        submission_id=submission_id, is_correct=option.is_correct, points_awarded=points,
        question_snapshot=question_snapshot(question, option),
    )
    if option.is_correct:
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.add_points(points)
    return attempt
