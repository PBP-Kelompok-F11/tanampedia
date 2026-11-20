from django.urls import path

from . import views

app_name = 'journal'

urlpatterns = [
    path('', views.show_journal_list, name='show_journal_list'),
    path('create/', views.create_journal_page, name='create_journal_page'),
    path('create/submit/', views.create_journal, name='create_journal'),
    path('<uuid:pk>/edit/', views.edit_journal, name='edit_journal'),
    path('<uuid:journal_pk>/entries/<uuid:entry_pk>/edit/', views.edit_entry, name='edit_entry'),
    path('<uuid:journal_pk>/entries/<uuid:entry_pk>/delete/', views.delete_entry, name='delete_entry'),
    path('<uuid:pk>/delete/', views.delete_journal_page, name='delete_page'),
    path('<uuid:pk>/delete/submit/', views.delete_journal, name='delete'),
    path('<uuid:journal_pk>/entries/create/', views.create_entry_page, name='create_entry_page'),
    path('<uuid:journal_pk>/entries/create/submit/',views.create_entry,name='create_entry'),
    path('<uuid:pk>/like/', views.toggle_journal_like, name='toggle_journal_like'),
    path('<uuid:pk>/', views.show_journal_detail, name='show_journal_detail'),
]
