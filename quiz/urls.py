from django.urls import path

from . import views

app_name = 'quiz'

urlpatterns = [
    path('', views.today, name='today'),
    path('soal/', views.question_list, name='question_list'),
    path('soal/tambah/', views.question_create, name='question_create'),
    path('soal/<int:pk>/edit/', views.question_update, name='question_update'),
    path('soal/<int:pk>/hapus/', views.question_delete, name='question_delete'),
]
