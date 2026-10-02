from django.shortcuts import render


def home(request):
    return render(request, 'home.html')


def design_system(request):
    return render(request, 'design_system.html')
