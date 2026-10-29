from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import RegisterForm


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
    return render(request, 'accounts/profile.html', {'profile': request.user.profile})
