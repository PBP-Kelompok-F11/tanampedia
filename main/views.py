import random

from django.db.models import Count
from django.http import Http404
from django.shortcuts import render

from accounts.models import Profile
from journal.models import PlantJournal

from . import trefle

HERO_IMAGES = [
    'img/hero/landing-1.jpg',
    'img/hero/landing-2.jpg',
    'img/hero/landing-3.jpg',
]


def home(request):
    hero_image = random.choice(HERO_IMAGES)

    community_journals = list(
        PlantJournal.objects
        .filter(is_public=True)
        .select_related('user', 'user__profile')
        .annotate(likes_count=Count('likes', distinct=True))[:3]
    )
    for journal in community_journals:
        journal.cover_image = journal.thumbnail

    return render(request, 'home.html', {
        'hero_image': hero_image,
        'community_journals': community_journals,
    })


def design_system(request):
    return render(request, 'design_system.html')


def leaderboard(request):
    top_profiles = (
        Profile.objects
        .select_related('user')
        .order_by('-pedia_points', 'user__username')[:10]
    )
    return render(request, 'leaderboard.html', {'top_profiles': top_profiles})


def _parse_page(raw_page):
    try:
        page = int(raw_page)
    except (TypeError, ValueError):
        return 1
    return page if page > 0 else 1


# Menampilkan daftar tanaman dengan fitur pencarian, sorting, dan pagination
def katalog_list(request):
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'name_asc')
    if sort not in {'name_asc', 'name_desc'}:
        sort = 'name_asc'
    page = _parse_page(request.GET.get('page', '1'))

    plants, meta, error_message = [], {}, None
    try:
        if query:
            plants, meta = trefle.search_plants(query, page=page)
        else:
            plants, meta = trefle.list_plants(page=page)
    except trefle.TrefleError as exc:
        error_message = exc.message

    # Sorting hanya diterapkan pada data di halaman yang sedang ditampilkan
    plants = sorted(
        plants,
        key=lambda plant: (plant.get('scientific_name') or plant.get('common_name') or '').casefold(),
        reverse=sort == 'name_desc',
    )
    per_page = (meta or {}).get('per_page') or 20
    total = (meta or {}).get('total')
    current_count = len(plants)
    if total is not None:
        try:
            total = max(int(total), 0)
        except (TypeError, ValueError):
            total = None
    start_index = ((page - 1) * per_page + 1) if current_count else 0
    end_index = ((page - 1) * per_page + current_count) if current_count else 0

    has_next = bool(total is not None and page * per_page < total)

    context = {
        'query': query,
        'plants': plants,
        'meta': meta or {},
        'page': page,
        'sort': sort,
        'result_start': start_index,
        'result_end': end_index,
        'result_total': total,
        'has_prev': page > 1,
        'has_next': has_next,
        'error_message': error_message,
    }
    return render(request, 'katalog/list.html', context)


# Menampilkan detail tanaman berdasarkan slug dari Trefle
def katalog_detail(request, slug):
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
        'care_cards': trefle.extract_care_cards(plant),
        'error_message': None,
    }
    return render(request, 'katalog/detail.html', context)
