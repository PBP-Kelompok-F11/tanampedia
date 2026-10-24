import random

from django.shortcuts import render

HERO_IMAGES = [
    'img/hero/landing-1.jpg',
    'img/hero/landing-2.jpg',
    'img/hero/landing-3.jpg',
]


def home(request):
    return render(request, 'home.html', {'hero_image': random.choice(HERO_IMAGES)})


def design_system(request):
    return render(request, 'design_system.html')
