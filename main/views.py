import random

from django.http import Http404
from django.shortcuts import render

from . import trefle

HERO_IMAGES = [
    'img/hero/landing-1.jpg',
    'img/hero/landing-2.jpg',
    'img/hero/landing-3.jpg',
]


def home(request):
    return render(request, 'home.html', {'hero_image': random.choice(HERO_IMAGES)})


def design_system(request):
    return render(request, 'design_system.html')


def _parse_page(raw_page):
    try:
        page = int(raw_page)
    except (TypeError, ValueError):
        return 1
    return page if page > 0 else 1


def katalog_list(request):
    """Katalog Tanaman: browse/search plants sourced from the Trefle API."""
    query = request.GET.get('q', '').strip()
    page = _parse_page(request.GET.get('page', '1'))

    plants, meta, error_message = [], {}, None
    try:
        if query:
            plants, meta = trefle.search_plants(query, page=page)
        else:
            plants, meta = trefle.list_plants(page=page)
    except trefle.TrefleError as exc:
        error_message = exc.message

    has_next = bool((meta or {}).get('total')) and (
        page * (meta.get('per_page') or 20) < (meta.get('total') or 0)
    )

    context = {
        'query': query,
        'plants': plants,
        'meta': meta or {},
        'page': page,
        'has_prev': page > 1,
        'has_next': has_next,
        'error_message': error_message,
    }
    return render(request, 'katalog/list.html', context)


def katalog_detail(request, slug):
    """Katalog Tanaman detail page for a single species, by Trefle slug."""
    try:
        plant = trefle.get_plant_detail(slug)
    except trefle.TrefleError as exc:
        return render(request, 'katalog/detail.html', {
            'slug': slug,
            'plant': None,
            'care': [],
            'error_message': exc.message,
        })

    if plant is None:
        raise Http404("Tanaman tidak ditemukan di katalog Trefle.")

    context = {
        'plant': plant,
        'care': trefle.extract_care_info(plant),
        'error_message': None,
    }
    return render(request, 'katalog/detail.html', context)
