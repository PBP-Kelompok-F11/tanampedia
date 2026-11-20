from django.urls import path

from . import views

app_name = 'quiz_api'

urlpatterns = [
    path('', views.quiz_today, name='today'),
    path('jawab/', views.quiz_answer, name='answer'),
]
