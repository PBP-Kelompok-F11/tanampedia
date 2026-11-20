from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from django.db.models import Count
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from forum.models import Question, Answer
from forum.permission import IsAuthorOrReadOnly, IsNotAuthorForUpvote
from forum.serializer import AuthorSerializer, QuestionSerializer, AnswerSerializer

class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return

@api_view(["GET", "HEAD", "POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthorOrReadOnly])
def question_list(request):
    if request.method in ("GET", "HEAD"):
        questions = (
            Question.objects
            .select_related("author")
            .annotate(num_answers=Count("answers", distinct=True))
            .order_by("-created_at")
        )

        title_query = request.query_params.get("title", "").strip()
        if title_query:
            questions = questions.filter(title__icontains=title_query)

        serializer = QuestionSerializer(
            questions, many=True, context={"request": request}
        )
        return Response(serializer.data)

    serializer = QuestionSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save(author=request.user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(["GET", "HEAD", "POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthorOrReadOnly])
def answer_list(request, pk):
    question = get_object_or_404(Question.objects.select_related("author"), pk=pk)
    if request.method in ("GET", "HEAD"):
        answers = (
            question.answers
            .select_related("author", "question", "question__author")
            .prefetch_related("upvotes")
            .order_by("-created_at")
        )

        serializer = AnswerSerializer(
            answers, many=True, context={"request": request}
        )
        return Response(serializer.data)

    serializer = AnswerSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save(author=request.user, question = question)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsNotAuthorForUpvote])
def upvote_answer(request, pk):
    answer = get_object_or_404(Answer.objects.select_related("author"), pk=pk)

    if answer.author == request.user:
        return Response({"error": "Self-vote not allowed"}, status=status.HTTP_403_FORBIDDEN)

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

    return Response({
        "status": "success",
        "is_upvoted": is_upvoted,
        "upvote_count": answer.upvotes.count(),
        "upvoted_by_names": ", ".join(u.username for u in answer.upvotes.all()),
    }, status=status.HTTP_200_OK)

@api_view(["DELETE", "POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def delete_answer(request, pk):
    answer = get_object_or_404(Answer.objects.select_related("author"), pk=pk)
    question = answer.question

    if answer.author != request.user:
        return Response({"error": "User has no authority to delete"}, status=status.HTTP_403_FORBIDDEN)

    answer.delete()
    return Response({
        "status": "success",
        "total_answers": question.answers.count()
    }, status=status.HTTP_200_OK,)

@api_view(["GET", "HEAD", "PUT", "PATCH", "DELETE"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthorOrReadOnly])
def question_detail(request, pk):
    question = get_object_or_404(Question.objects.select_related("author"), pk=pk)

    if request.method in ("GET", "HEAD"):
        serializer = QuestionSerializer(question, context={"request": request})
        return Response(serializer.data)

    if question.author != request.user:
        return Response(
            {"error": "Anda tidak memiliki izin untuk mengubah atau menghapus pertanyaan ini."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method in ("PUT", "PATCH"):
        serializer = QuestionSerializer(
            question,
            data=request.data,
            partial=(request.method == "PATCH"),
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    question.delete()
    return Response(
        {"status": "success", "message": "Pertanyaan berhasil dihapus."},
        status=status.HTTP_200_OK,
    )