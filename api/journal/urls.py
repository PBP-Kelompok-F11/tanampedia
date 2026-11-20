from django.urls import path

from . import views

app_name = 'journal_api'

urlpatterns = [
    path('', views.journal_list_create, name='journal-list'),
    path('me/', views.my_journals, name='my-journals'),
    path('<uuid:pk>/', views.journal_detail, name='journal-detail'),
    path('<uuid:pk>/like/', views.journal_like, name='journal-like'),
    path('<uuid:journal_pk>/entries/', views.entry_list, name='entry-list'),
    path('<uuid:journal_pk>/entries/<uuid:entry_pk>/', views.entry_detail, name='entry-detail'),
]
