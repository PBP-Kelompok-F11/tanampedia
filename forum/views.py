from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Question, Answer
from .forms import QuestionForms, AnswerForms
from django.views.decorators.http import require_POST

def forum_home(request):
    questions = Question.objects.all().order_by('-created_at')
    return render(request, 'forum/forum_home.html', {'questions': questions})

def question_detail(request, pk):
    question = get_object_or_404(Question, pk=pk)
    answers = question.answers.all().order_by('-created_at')

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')
        form = AnswerForms(request.POST)
        if form.is_valid():
            answer = form.save(commit=False)
            answer.author = request.user
            answer.question = question
            answer.save()
            return redirect('question_detail', pk=question.pk)
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
            return redirect('question_detail', pk=question.pk)
    else:
        form = QuestionForms()

    return render(request, 'forum/create_question.html', {'form': form})

@login_required
@require_POST
def upvote_answer(request, pk):
    answer = get_object_or_404(Answer, pk=pk)

    if answer.author == request.user:
        return redirect('question_detail:', pk=answer.question.pk)

    if request.user in answer.upvotes.all():
        answer.upvotes.remove(request.user)
        if hasattr(answer.author, 'profile'):
            answer.author.profile.add_points(-1)
    else:
        answer.upvotes.add(request.user)
        if hasattr(answer.author, 'profile'):
            answer.author.profile.add_points(1)

    return redirect('question_detail', pk=answer.question.pk)