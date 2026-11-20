from django.urls import path

from . import api_views

urlpatterns = [
    path("register/", api_views.register, name="register"),
    path("login/", api_views.login, name="login"),
    path("logout/", api_views.logout, name="logout"),
    path("profile/", api_views.profile, name="profile"),
    path("profiles/", api_views.profile_list, name="profile-list"),
    path("profiles/<int:profile_id>/", api_views.profile_detail, name="profile-detail"),
]
