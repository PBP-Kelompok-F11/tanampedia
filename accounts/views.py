from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import ProfileEditForm, RegisterForm


def _safe_next(request, next_url):
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return None


def register(request):
    form = RegisterForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Akun berhasil dibuat. Silakan masuk.')
        return redirect('accounts:login')

    return render(request, 'accounts/register.html', {'form': form})


def login_user(request):
    next_url = _safe_next(request, request.POST.get('next') or request.GET.get('next'))
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect(next_url or 'accounts:profile')

    return render(request, 'accounts/login.html', {'form': form, 'next': next_url or ''})


def logout_user(request):
    logout(request)
    return redirect('main:home')


@login_required
def profile(request):
    return render(request, 'accounts/profile.html', {
        'profile': request.user.profile,
        'edit_form': ProfileEditForm(instance=request.user.profile),
    })


@login_required
@require_POST
def edit_profile(request):
    form = ProfileEditForm(request.POST, instance=request.user.profile)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)

    profile = form.save()
    return JsonResponse({
        'display_name': profile.display_name,
        'display_name_or_username': profile.display_name_or_username,
        'bio': profile.bio,
        'profile_picture_url': profile.profile_picture_url,
    }, status=200)
