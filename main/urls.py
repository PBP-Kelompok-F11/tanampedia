from django.urls import path

from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),
    path('ds', views.design_system, name='design_system'),
    path('katalog/', views.katalog_list, name='katalog_list'),
    path('katalog/<slug:slug>/', views.katalog_detail, name='katalog_detail'),
]
