from django.urls import path
from . import api_views

app_name = "api"
urlpatterns = [
    path("question/", api_views.question_list, name="question-list"),
    path("question/<int:pk>/", api_views.question_detail, name="question-detail"),
    path("question/<int:pk>/answer/", api_views.answer_list, name="answer-list"),
    path("answer/<int:pk>/delete", api_views.delete_answer, name="delete-answer"),
    path("answer/<int:pk>/upvote", api_views.upvote_answer, name="upvote-answer"),
]