from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from .models import Question, Answer
from .forms import QuestionForms, AnswerForms
from django.views.decorators.http import require_POST

def forum_home(request):
    title_query = request.GET.get("title", "").strip()
    questions = Question.objects.all().order_by('-created_at')

    if title_query:
        questions = questions.filter(title__icontains=title_query)

    context = {
        "title_query": title_query,
        "questions": questions,
    }
    return render(request, 'forum/forum_home.html', context)

def question_detail(request, pk):
    question = get_object_or_404(Question, pk=pk)
    answers = question.answers.all().order_by('-created_at')

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        form = AnswerForms(request.POST)
        if form.is_valid():
            answer = form.save(commit=False)
            answer.author = request.user
            answer.question = question
            answer.save()
            return redirect('forum:question_detail', pk=question.pk)
    else:
        form = AnswerForms()

    return render(request, 'forum/question_detail.html', {
        'question': question,
        'answers': answers,
        'form': form
    })


@login_required
def create_question(request):
    if request.method == 'POST':
        form = QuestionForms(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.author = request.user
            question.save()
            return redirect('forum:question_detail', pk=question.pk)
    else:
        form = QuestionForms()

    return render(request, 'forum/create_question.html', {'form': form})

@login_required
@require_POST
def upvote_answer(request, pk):
    answer = get_object_or_404(Answer, pk=pk)

    if answer.author == request.user:
        return redirect('forum:question_detail', pk=answer.question.pk)

    if request.user in answer.upvotes.all():
        answer.upvotes.remove(request.user)
        if hasattr(answer.author, 'profile'):
            answer.author.profile.add_points(-1)
    else:
        answer.upvotes.add(request.user)
        if hasattr(answer.author, 'profile'):
            answer.author.profile.add_points(1)

    return redirect('forum:question_detail', pk=answer.question.pk)