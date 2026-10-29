from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_http_methods

from .forms import JournalEntryForm, PlantJournalForm
from .models import JournalEntry, JournalLike, PlantJournal


def _profile_context(user):
    profile = user.profile
    return {
        'level_title': profile.level['title'],
        'pedia_points': profile.pedia_points,
    }

@login_required
@ensure_csrf_cookie
def show_journal_list(request):
    tab = request.GET.get('tab', 'my')
    journals = PlantJournal.objects.select_related(
        'user',
        'user__profile',
    ).annotate(
        likes_count=Count('likes', distinct=True),
        is_liked=Exists(
            JournalLike.objects.filter(
                journal_id=OuterRef('pk'),
                user=request.user,
            )
        ),
    ).prefetch_related(
        Prefetch(
            'entries',
            queryset=JournalEntry.objects.order_by('-created_at', '-pk').only(
                'journal_id',
                'image',
                'created_at',
            ),
            to_attr='latest_entries',
        )
    )
    if tab == 'for-you':
        journals = journals.filter(is_public=True).exclude(user=request.user)
    else:
        tab = 'my'
        journals = journals.filter(user=request.user)

    journals = list(journals)
    for journal in journals:
        journal.entry_count = len(journal.latest_entries)
        journal.cover_image = journal.thumbnail or next((entry.image for entry in journal.latest_entries if entry.image), '')
        journal.last_activity = journal.latest_entries[0].created_at if journal.latest_entries else None

    context = {
        'journals': journals,
        'active_tab': tab,
        **_profile_context(request.user),
    }
    return render(request, 'journal/list.html', context)

@login_required
def create_journal_page(request):
    context = {
        'journal_form': PlantJournalForm(),
        'status_options': [
            {'value': value, 'label': label}
            for value, label in PlantJournal.Status.choices
        ],
        'status_default_value': PlantJournal.Status.ACTIVE,
        'status_default_label': PlantJournal.Status.ACTIVE.label,
        **_profile_context(request.user),
    }
    return render(request, 'journal/create.html', context)

@login_required
@ensure_csrf_cookie
def show_journal_detail(request, pk):
    journal = get_object_or_404(
        PlantJournal.objects.select_related(
            'user',
            'user__profile',
        ).annotate(
            likes_count=Count('likes', distinct=True),
            is_liked=Exists(
                JournalLike.objects.filter(
                    journal_id=OuterRef('pk'),
                    user=request.user,
                )
            ),
        ),
        pk=pk,
    )
    if not journal.is_public and journal.user_id != request.user.pk:
        raise Http404

    entries = list(journal.entries.all())
    context = {
        'journal': journal,
        'entries': entries,
        'entry_count': len(entries),
        'cover_image': journal.thumbnail,
        **_profile_context(request.user),
    }
    return render(request, 'journal/detail.html', context)

@login_required
def create_entry_page(request, journal_pk):
    journal = get_object_or_404(
        PlantJournal,
        pk=journal_pk,
        user=request.user,
    )
    context = {
        'journal': journal,
        'entry_form': JournalEntryForm(),
        'condition_options': [
            {'value': value, 'label': label}
            for value, label in JournalEntry.PlantCondition.choices
        ],
        **_profile_context(request.user),
    }
    return render(request, 'journal/entry_create.html', context)

@login_required
@require_POST
@transaction.atomic
def create_journal(request):
    form = PlantJournalForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)

    journal = form.save(commit=False)
    journal.user = request.user
    journal.save()
    journal.cover_image = journal.thumbnail
    request.user.profile.add_points(20)
    return JsonResponse({
        'html': render(
            request,
            'journal/partials/journal_card.html',
            {'journal': journal},
        ).content.decode(),
        'url': reverse('journal:show_journal_detail', args=(journal.pk,)),
        'pedia_points': request.user.profile.pedia_points,
        'level_title': request.user.profile.level['title'],
    }, status=201)

@login_required
@require_POST
@transaction.atomic
def create_entry(request, journal_pk):
    journal = get_object_or_404(PlantJournal, pk=journal_pk, user=request.user)
    form = JournalEntryForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)

    entry = form.save(commit=False)
    entry.journal = journal
    entry.save()
    request.user.profile.add_points(5)
    return JsonResponse({
        'html': render(
            request,
            'journal/partials/entry_item.html',
            {'entry': entry},
        ).content.decode(),
        'url': reverse('journal:show_journal_detail', args=(journal.pk,)),
        'pedia_points': request.user.profile.pedia_points,
        'level_title': request.user.profile.level['title'],
    }, status=201)


@login_required
@require_http_methods(['GET', 'POST'])
def edit_journal(request, pk):
    journal = get_object_or_404(PlantJournal, pk=pk, user=request.user)
    form = PlantJournalForm(
        request.POST if request.method == 'POST' else None,
        instance=journal,
    )
    if request.method == 'POST':
        if not form.is_valid():
            return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
        form.save()
        return JsonResponse({
            'url': reverse('journal:show_journal_detail', args=(journal.pk,)),
        })

    return render(request, 'journal/create.html', {
        'journal': journal,
        'journal_form': form,
        'status_options': [
            {'value': value, 'label': label}
            for value, label in PlantJournal.Status.choices
        ],
        'status_default_value': journal.status,
        'status_default_label': journal.get_status_display(),
        **_profile_context(request.user),
    })


@login_required
@require_http_methods(['GET'])
def delete_journal_page(request, pk):
    journal = get_object_or_404(PlantJournal, pk=pk, user=request.user)
    return render(request, 'journal/delete.html', {'journal': journal})


@login_required
@require_POST
def delete_journal(request, pk):
    journal = get_object_or_404(PlantJournal, pk=pk, user=request.user)
    # Existing CASCADE relationships remove entries and likes. Images are
    # external URLs, so there are no locally stored files to delete.
    journal.delete()
    if 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse({'url': reverse('journal:show_journal_list')})
    return redirect('journal:show_journal_list')


@login_required
@require_http_methods(['GET', 'POST'])
def edit_entry(request, journal_pk, entry_pk):
    journal = get_object_or_404(PlantJournal, pk=journal_pk, user=request.user)
    entry = get_object_or_404(JournalEntry, pk=entry_pk, journal=journal)
    form = JournalEntryForm(request.POST if request.method == 'POST' else None, instance=entry)
    if request.method == 'POST':
        if not form.is_valid():
            return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
        form.save()
        return JsonResponse({'url': reverse('journal:show_journal_detail', args=[journal.pk])})
    return render(request, 'journal/entry_create.html', {
        'journal': journal,
        'entry': entry,
        'entry_form': form,
        'condition_options': [
            {'value': value, 'label': label}
            for value, label in JournalEntry.PlantCondition.choices
        ],
        'condition_value': entry.plant_condition,
        'condition_label': entry.get_plant_condition_display(),
        **_profile_context(request.user),
    })


@login_required
@require_http_methods(['GET', 'POST'])
def delete_entry(request, journal_pk, entry_pk):
    journal = get_object_or_404(PlantJournal, pk=journal_pk, user=request.user)
    entry = get_object_or_404(JournalEntry, pk=entry_pk, journal=journal)
    if request.method == 'POST':
        entry.delete()
        if 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({'deleted': str(entry_pk), 'entry_count': journal.entries.count()})
        return redirect('journal:show_journal_detail', pk=journal.pk)
    return render(request, 'journal/entry_delete.html', {'journal': journal, 'entry': entry})


@login_required
@require_POST
def toggle_journal_like(request, pk):
    with transaction.atomic():
        journal = get_object_or_404(
            PlantJournal.objects.select_for_update(),
            pk=pk,
        )
        if not journal.is_public and journal.user_id != request.user.pk:
            raise Http404

        like = JournalLike.objects.filter(journal=journal, user=request.user)
        if like.exists():
            like.delete()
            liked = False
        else:
            JournalLike.objects.create(journal=journal, user=request.user)
            liked = True

        likes_count = JournalLike.objects.filter(journal=journal).count()

    return JsonResponse({
        'liked': liked,
        'likes_count': likes_count,
    })
