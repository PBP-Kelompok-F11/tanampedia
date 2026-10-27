from django.urls import path
from . import views

app_name = 'forum'

urlpatterns = [
    path('', views.forum_home, name='forum_home'),
    path('ask/', views.create_question, name='create_question'),
    path('<int:pk>/', views.question_detail, name='question_detail'),
    path('answer/<int:pk>/upvote/', views.upvote_answer, name='upvote_answer'),
]