from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import QuestionForm, question_has_history
from .models import DailyChallenge, Question, QuizAttempt
from .services import answer_token, daily_success, next_reset, process_answer, quiz_date


def superuser_required(view):
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return login_required(guarded)


@never_cache
@require_GET
def today(request):
    day = quiz_date()
    success = daily_success(request.user, day) if request.user.is_authenticated else None
    result = None
    result_id = request.session.pop('quiz_result_id', None)
    if request.user.is_authenticated and result_id:
        result = QuizAttempt.objects.filter(
            pk=result_id, user=request.user, quiz_date=day,
        ).select_related('selected_option__question').first()
    result = success or result
    question = result.selected_option.question if result else (
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
    token = (
        answer_token(question, request.user, day)
        if question and request.user.is_authenticated and not result else None
    )
    return render(request, 'quiz/today.html', {
        'question': question, 'answer_token': token, 'result': result,
        'cooldown': bool(success), 'reset_date': next_reset(day).date(),
        'reward_points': settings.QUIZ_CORRECT_ANSWER_POINTS,
    })


@never_cache
@login_required
@require_POST
def answer(request):
    try:
        attempt = process_answer(
            request.user, request.POST.get('answer_token'), request.POST.get('option'),
        )
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    except IntegrityError:
        if not daily_success(request.user, quiz_date()):
            raise
        messages.info(request, 'Hadiah kuis hari ini sudah diterima.')
    except OperationalError as error:
        if connection.vendor != 'sqlite' or 'locked' not in str(error).lower():
            raise
        messages.info(request, 'Jawaban sedang diproses. Silakan muat ulang halaman kuis.')
    else:
        request.session['quiz_result_id'] = attempt.pk
    return redirect('quiz:today')


@superuser_required
@require_GET
def question_list(request):
    questions = Question.objects.annotate(
        has_schedule=Exists(DailyChallenge.objects.filter(question_id=OuterRef('pk'))),
        has_answers=Exists(QuizAttempt.objects.filter(selected_option__question_id=OuterRef('pk'))),
    ).prefetch_related('options').order_by('-created_at', '-pk')
    page = Paginator(questions, 10).get_page(request.GET.get('page'))
    return render(request, 'quiz/question_list.html', {'page_obj': page})


@superuser_required
@require_http_methods(['GET', 'POST'])
def question_create(request):
    form = QuestionForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        form.instance.created_by = request.user
        form.save()
        messages.success(request, 'Soal kuis berhasil ditambahkan.')
        return redirect('quiz:question_list')
    return render(request, 'quiz/question_form.html', {'form': form, 'editing': False})


@superuser_required
@require_http_methods(['GET', 'POST'])
def question_update(request, pk):
    question = get_object_or_404(Question, pk=pk)
    form = QuestionForm(request.POST if request.method == 'POST' else None, instance=question)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Soal kuis berhasil diperbarui.')
            return redirect('quiz:question_list')
    return render(request, 'quiz/question_form.html', {'form': form, 'editing': True})


@superuser_required
@require_http_methods(['GET', 'POST'])
def question_delete(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            question = get_object_or_404(Question.objects.select_for_update(), pk=pk)
            if question_has_history(question):
                messages.error(request, 'Soal yang sudah digunakan tidak dapat dihapus. Nonaktifkan soal melalui Edit.')
            else:
                try:
                    with transaction.atomic():
                        question.delete()
                except ProtectedError:
                    messages.error(request, 'Soal sudah digunakan dan tidak dapat dihapus.')
                else:
                    messages.success(request, 'Soal kuis berhasil dihapus.')
        return redirect('quiz:question_list')
    return render(request, 'quiz/question_confirm_delete.html', {
        'question': question, 'is_locked': question_has_history(question),
    })
