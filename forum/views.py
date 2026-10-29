from django.shortcuts import render, get_object_or_404, redirect, resolve_url
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.urls import reverse
from django.db.models import Count
from django.conf import settings
from .models import Question, Answer
from .forms import QuestionForms, AnswerForms


def _is_ajax(request):
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


def _get_author_info(user):
    profile = getattr(user, "profile", None)
    name = (
        profile.display_name_or_username
        if profile and hasattr(profile, "display_name_or_username")
        else user.username
    )
    level_title = ""
    if profile and hasattr(profile, "level") and profile.level:
        lvl = profile.level
        level_title = str(lvl.title) if hasattr(lvl, "title") and not callable(lvl.title) else str(lvl)
    return name, level_title


def forum_home(request):
    title_query = request.GET.get("title", "").strip()
    questions = (
        Question.objects
        .annotate(num_answers=Count("answers", distinct=True))
        .order_by('-created_at')
    )

    if title_query:
        questions = questions.filter(title__icontains=title_query)

    context = {
        "title_query": title_query,
        "questions": questions,
        "form": QuestionForms(),
        "login_url": resolve_url(settings.LOGIN_URL),
    }
    return render(request, 'forum/forum_home.html', context)


def question_detail(request, pk):
    question = get_object_or_404(Question, pk=pk)
    answers = question.answers.all().order_by('-created_at')

    if request.method == 'POST':
        if not request.user.is_authenticated:
            if _is_ajax(request):
                return JsonResponse({"error": "Unauthorized"}, status=401)
            return redirect(settings.LOGIN_URL)

        form = AnswerForms(request.POST)
        if form.is_valid():
            answer = form.save(commit=False)
            answer.author = request.user
            answer.question = question
            answer.save()

            if _is_ajax(request):
                author_name, _ = _get_author_info(request.user)
                return JsonResponse({
                    "status": "success",
                    "answer": {
                        "id": answer.pk,
                        "content": answer.content,
                        "author": author_name,
                        "avatar_initials": author_name[:2].upper(),
                        "created_at": "baru saja",
                        "total_upvotes": 0,
                    },
                    "total_answers": question.answers.count()
                }, status=201)

            return redirect("forum:question_detail", pk=question.pk)
        else:
            if _is_ajax(request):
                return JsonResponse({"status": "error", "errors": form.errors}, status=400)
    else:
        form = AnswerForms()

    context = {
        'question': question,
        'answers': answers,
        'form': form,
        'login_url': resolve_url(settings.LOGIN_URL),
    }
    return render(request, 'forum/question_detail.html', context)


@login_required
def create_question(request):
    if request.method == "POST":
        form = QuestionForms(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.author = request.user
            question.save()

            if _is_ajax(request):
                author_name, level_title = _get_author_info(request.user)
                return JsonResponse({
                    "status": "success",
                    "question": {
                        "id": question.pk,
                        "title": question.title,
                        "content": question.content,
                        "author": author_name,
                        "avatar_initials": author_name[:2].upper(),
                        "level": level_title,
                        "created_at": "baru saja",
                        "detail_url": reverse("forum:question_detail", args=[question.pk]),
                    }
                }, status=201)

            return redirect("forum:question_detail", pk=question.pk)
        else:
            if _is_ajax(request):
                return JsonResponse({"status": "error", "errors": form.errors}, status=400)
    else:
        form = QuestionForms()

    return render(request, 'forum/create_question.html', {
        'form': form,
        'question': None,
        'is_edit': False,
    })


@login_required
def edit_question(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if question.author != request.user:
        if _is_ajax(request):
            return JsonResponse({"error": "Forbidden"}, status=403)
        raise PermissionDenied("Anda tidak memiliki izin untuk mengedit pertanyaan ini.")

    if request.method == "POST":
        form = QuestionForms(request.POST, instance=question)
        if form.is_valid():
            form.save()
            if _is_ajax(request):
                return JsonResponse({
                    "status": "success",
                    "title": question.title,
                    "content": question.content,
                })
            return redirect("forum:question_detail", pk=question.pk)
        else:
            if _is_ajax(request):
                return JsonResponse({"status": "error", "errors": form.errors}, status=400)
    else:
        form = QuestionForms(instance=question)

    context = {
        "form": form,
        "question": question,
        "is_edit": True,
    }
    return render(request, "forum/create_question.html", context)


@login_required
@require_POST
def delete_question(request, pk):
    question = get_object_or_404(Question, pk=pk)

    if question.author != request.user:
        if _is_ajax(request):
            return JsonResponse({"error": "Forbidden"}, status=403)
        raise PermissionDenied("Anda tidak memiliki izin untuk menghapus pertanyaan ini.")

    question.delete()
    if _is_ajax(request):
        return JsonResponse({"status": "success", "redirect_url": reverse("forum:forum_home")})
    return redirect("forum:forum_home")


@login_required
@require_POST
def upvote_answer(request, pk):
    answer = get_object_or_404(Answer, pk=pk)

    if answer.author == request.user:
        if _is_ajax(request):
            return JsonResponse({"error": "Self-vote not allowed"}, status=400)
        return redirect("forum:question_detail", pk=answer.question.pk)

    if request.user in answer.upvotes.all():
        answer.upvotes.remove(request.user)
        is_upvoted = False
        point_delta = -1
    else:
        answer.upvotes.add(request.user)
        is_upvoted = True
        point_delta = 1

    if hasattr(answer.author, 'profile'):
        profile = answer.author.profile
        profile.pedia_points = max(0, profile.pedia_points + point_delta)
        profile.save()

    if _is_ajax(request):
        return JsonResponse({
            "status": "success",
            "is_upvoted": is_upvoted,
            "total_upvotes": answer.total_upvotes,
        })

    return redirect('forum:question_detail', pk=answer.question.pk)

@login_required
@require_POST
def delete_answer(request, pk):
    answer = get_object_or_404(Answer, pk=pk)
    question_pk = answer.question

    if answer.author != request.user:
        if _is_ajax(request):
            return JsonResponse({"error": "Forbidden"}, status=403)
        raise PermissionDenied("Anda tidak memiliki izin untuk menghapus jawaban ini.")

    answer.delete()
    if _is_ajax(request):
        return JsonResponse({
            "status": "success",
            "total_answers": question_pk.answers.count()
        })
    return redirect("forum:question_detail", pk=question_pk.pk)