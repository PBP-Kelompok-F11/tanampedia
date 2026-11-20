from django.urls import path
from . import views

app_name = 'forum'

urlpatterns = [
    path('', views.forum_home, name='forum_home'),
    path('ask/', views.create_question, name='create_question'),
    path('<int:pk>/', views.question_detail, name='question_detail'),
    path('<int:pk>/edit/', views.edit_question, name='edit_question'),
    path('<int:pk>/delete/', views.delete_question, name='delete_question'),
    path('answer/<int:pk>/upvote/', views.upvote_answer, name='upvote_answer'),
    path('answer/<int:pk>/delete/', views.delete_answer, name='delete_answer'),
]