from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, connection
from django.db.models import Count, Q
from django.views.decorators.cache import never_cache

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view, authentication_classes, parser_classes, permission_classes,
)
from rest_framework.parsers import JSONParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from quiz.models import Question
from quiz.services import answer_token, daily_success, next_reset, process_answer, quiz_date

from .serializers import (
    QuizAnswerSerializer, QuizTodaySerializer,
    question_payload, result_payload,
)


def _eligible_question():
    return (
        Question.objects.filter(is_active=True)
        .annotate(
            option_count=Count('options'),
            correct_count=Count('options', filter=Q(options__is_correct=True)),
        )
        .filter(option_count=4, correct_count=1)
        .order_by('?')
        .prefetch_related('options')
        .first()
    )


def _status_payload(day, success, result):
    return {
        'answered': bool(result),
        'answered_correctly': bool(success),
        'next_reset': next_reset(day).date(),
        'reward_points': settings.QUIZ_CORRECT_ANSWER_POINTS,
    }


@api_view(['GET', 'HEAD'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
@never_cache
def quiz_today(request):
    day = quiz_date()
    success = daily_success(request.user, day)
    result = success
    if result:
        data = {
            'status': _status_payload(day, success, result),
            'question': None,
            'answer_token': None,
            'result': result_payload(result),
        }
    else:
        question = _eligible_question()
        data = {
            'status': _status_payload(day, success, None),
            'question': question_payload(question) if question else None,
            'answer_token': answer_token(question, request.user, day) if question else None,
            'result': None,
        }
    return Response(QuizTodaySerializer(data).data)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, FormParser])
def quiz_answer(request):
    serializer = QuizAnswerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        attempt = process_answer(
            request.user,
            serializer.validated_data['answer_token'],
            serializer.validated_data['option'],
        )
    except ValidationError as error:
        return Response({'error': ' '.join(error.messages)}, status=status.HTTP_400_BAD_REQUEST)
    except IntegrityError:
        if not daily_success(request.user, quiz_date()):
            raise
        return Response({
            'error': 'Reward PediaPoints hari ini sudah diterima. Muat ulang halaman kuis.',
        }, status=status.HTTP_409_CONFLICT)
    except OperationalError as error:
        if connection.vendor != 'sqlite' or 'locked' not in str(error).lower():
            raise
        return Response({
            'error': 'Jawaban sedang diproses. Silakan coba lagi atau muat ulang halaman kuis.',
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    day = quiz_date()
    success = daily_success(request.user, day)
    result = success or attempt
    reward_received = success is None or success.pk == attempt.pk
    return Response({
        'result': result_payload(result),
        'reward_received': reward_received,
        'next_reset': next_reset(day).date(),
    })
