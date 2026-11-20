from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .forms import RegisterForm
from .models import Profile
from .serializers import ProfileSerializer


def _serialize_profile(profile):
    return {
        "display_name": profile.display_name_or_username,
        "bio": profile.bio,
        "profile_picture_url": profile.profile_picture_url,
        "pedia_points": profile.pedia_points,
        "level": profile.level["title"],
    }


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([AllowAny])
def register(request):
    form = RegisterForm(request.data)
    if not form.is_valid():
        return Response({
            "status": False,
            "message": "Registrasi gagal.",
            "errors": form.errors.get_json_data(),
        }, status=status.HTTP_400_BAD_REQUEST)

    user = form.save()
    return Response({
        "status": True,
        "username": user.username,
        "message": "User berhasil dibuat!",
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response({
            "status": False,
            "message": "Login gagal, periksa kembali username atau password.",
        }, status=status.HTTP_401_UNAUTHORIZED)

    auth_login(request, user)
    return Response({
        "status": True,
        "username": user.username,
        "message": "Login sukses!",
        **_serialize_profile(user.profile),
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def logout(request):
    username = request.user.username
    auth_logout(request)
    return Response({
        "status": True,
        "username": username,
        "message": "Logout berhasil!",
    }, status=status.HTTP_200_OK)


@api_view(["GET", "HEAD"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def profile(request):
    return Response({
        "status": True,
        "username": request.user.username,
        **_serialize_profile(request.user.profile),
    }, status=status.HTTP_200_OK)


@api_view(["GET", "HEAD"])
@authentication_classes([SessionAuthentication])
@permission_classes([AllowAny])
def profile_list(request):
    profiles = Profile.objects.select_related("user").order_by("-pedia_points", "user__username")

    username = request.query_params.get("username", "").strip()
    if username:
        profiles = profiles.filter(user__username__icontains=username)

    return Response(ProfileSerializer(profiles, many=True).data)


@api_view(["GET", "HEAD", "PUT", "PATCH"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticatedOrReadOnly])
def profile_detail(request, profile_id):
    target_profile = get_object_or_404(Profile.objects.select_related("user"), pk=profile_id)

    if request.method in ("GET", "HEAD"):
        return Response(ProfileSerializer(target_profile).data)

    if target_profile.user_id != request.user.id:
        return Response(
            {"detail": "Kamu hanya bisa mengubah profil milikmu sendiri."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = ProfileSerializer(
        target_profile, data=request.data, partial=request.method == "PATCH",
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)
