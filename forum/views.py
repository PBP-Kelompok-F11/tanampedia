from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Question, Answer
from .forms import QuestionForms, AnswerForms
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.urls import reverse

def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')

def forum_home(request):
    title_query = request.GET.get("title", "").strip()
    questions = Question.objects.all().order_by('-created_at')

    if title_query:
        questions = questions.filter(title__icontains=title_query)

    context = {
        "title_query": title_query,
        "questions": questions,
        "form": QuestionForms(),
    }
    return render(request, 'forum/forum_home.html', context)

def question_detail(request, pk):
    question = get_object_or_404(Question, pk=pk)
    answers = question.answers.all().order_by('-created_at')
    form = AnswerForms(request.POST or None )

    if request.method == 'POST' and form.is_valid():
        if not request.user.is_authenticated:
            if _is_ajax(request):
                return JsonResponse({"error": "Unauthorized"}, status=401)
            return redirect('login')
        answer = form.save(commit=False)
        answer.author = request.user
        answer.question = question
        answer.save()
        if _is_ajax(request):
            author_name = (
                request.user.profile.display_name_or_username
                if hasattr(request.user, "profile") else request.user.username
            )
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

    context = {
        'question': question,
        'answers': answers,
        'form': form
    }

    return render(request, 'forum/question_detail.html', context)


@login_required
def create_question(request):
    form = QuestionForms(request.POST or None)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.author = request.user
        question.save()
        if _is_ajax(request):
            author_name = (
                request.user.profile.display_name_or_username
                if hasattr(request.user, "profile") else request.user.username
            )
            author_level = (
                request.user.profile.level.title
                if hasattr(request.user, "profile") and hasattr(request.user.profile, "level") and request.user.profile.level else ""
            )
            return JsonResponse({
                "status": "success",
                "question": {
                    "id": question.pk,
                    "title": question.title,
                    "content": question.content,
                    "author": author_name,
                    "author_initials": author_name[:2].upper(),
                    "author_level": author_level,
                    "detail_url": reverse("forum:question_detail", args=[question.pk]),
                    "question": None,
                    "is_edit": False,
                }
            }, status=201)

        return redirect("forum:question_detail", pk=question.pk)
    else:
        if _is_ajax(request):
            return JsonResponse({"status": "error", "errors": form.errors}, status=400)

    return render(request, 'forum/create_question.html', {'form': form})

@login_required
def edit_question(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if question.author != request.user:
        if _is_ajax(request):
            return JsonResponse({"error": "Forbidden"}, status=403)
        raise PermissionDenied("Anda tidak memiliki izin untuk mengedit pertanyaan ini.")
    form = QuestionForms(request.POST or None, instance=question)
    if request.method == "POST" and form.is_valid():
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
        voted = False
        point_delta = -1
    else:
        answer.upvotes.add(request.user)
        voted = True
        point_delta = 1

    if hasattr(answer.author, 'profile'):
        profile = answer.author.profile
        profile.pedia_points = max(0, profile.pedia_points + point_delta)
        profile.save()

    if _is_ajax(request):
        return JsonResponse({
            "status": "success",
            "voted": voted,
            "total_upvotes": answer.total_upvotes,
        })

    return redirect('forum:question_detail', pk=answer.question.pk)

@login_required
@require_POST
def delete_answer(request, pk):
    answer = get_object_or_404(Answer, pk=pk)
    question_pk = answer.question.pk

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
    return redirect("forum:question_detail", pk=question_pk)