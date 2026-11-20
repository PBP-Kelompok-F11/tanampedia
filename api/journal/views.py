from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view, authentication_classes, parser_classes, permission_classes,
)
from rest_framework.parsers import JSONParser
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from journal.models import JournalEntry, JournalLike, PlantJournal

from .permissions import require_journal_owner
from .serializers import (
    JournalEntrySerializer, JournalListQuerySerializer, JournalListSerializer, PlantJournalSerializer,
)


def _visible_journals(user):
    return PlantJournal.objects.filter(Q(is_public=True) | Q(user=user))


def _with_like_stats(journals, user):
    return journals.annotate(
        likes_count=Count('likes'),
        is_liked=Exists(JournalLike.objects.filter(journal_id=OuterRef('pk'), user=user)),
    )


def _journal_list_response(request, journals):
    query = JournalListQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    params = query.validated_data

    journals = _with_like_stats(journals, request.user)
    search = params.get('search', params.get('q', ''))
    if search:
        journals = journals.filter(Q(plant_name__icontains=search) | Q(description__icontains=search))
    if params['status'] != 'all':
        journals = journals.filter(status=params['status'])
    if params['liked'] == '1':
        journals = journals.filter(is_liked=True)
    ordering = PlantJournal._meta.ordering
    if params['sort'] == 'most_liked':
        ordering = ('-likes_count', *ordering)
    return Response(JournalListSerializer(journals.order_by(*ordering), many=True).data)


def _journal_data(request, journals, pk):
    journal = get_object_or_404(_with_like_stats(journals, request.user), pk=pk)
    return PlantJournalSerializer(journal, context={'request': request}).data


@api_view(['GET', 'HEAD', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def journal_list_create(request):
    if request.method in SAFE_METHODS:
        return _journal_list_response(request, PlantJournal.objects.filter(is_public=True))

    serializer = PlantJournalSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        journal = serializer.save(user=request.user)
        request.user.profile.add_points(20)
        data = _journal_data(request, PlantJournal.objects.all(), journal.pk)
    return Response(data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'HEAD'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def my_journals(request):
    return _journal_list_response(request, PlantJournal.objects.filter(user=request.user))


@api_view(['GET', 'HEAD', 'PUT', 'PATCH', 'DELETE'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def journal_detail(request, pk):
    journals = _visible_journals(request.user)
    if request.method in SAFE_METHODS:
        return Response(_journal_data(request, journals, pk))

    with transaction.atomic():
        journal = get_object_or_404(journals.select_for_update(), pk=pk)
        require_journal_owner(request, journal)
        if request.method == 'DELETE':
            journal.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = PlantJournalSerializer(
            journal, data=request.data, partial=request.method == 'PATCH', context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(_journal_data(request, journals, pk))


@api_view(['GET', 'HEAD', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def entry_list(request, journal_pk):
    journals = _visible_journals(request.user)
    if request.method in SAFE_METHODS:
        journal = get_object_or_404(journals, pk=journal_pk)
        return Response(JournalEntrySerializer(journal.entries.all(), many=True).data)

    with transaction.atomic():
        journal = get_object_or_404(journals.select_for_update(), pk=journal_pk)
        require_journal_owner(request, journal)
        serializer = JournalEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(journal=journal)
        request.user.profile.add_points(5)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'HEAD', 'PUT', 'PATCH', 'DELETE'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def entry_detail(request, journal_pk, entry_pk):
    journals = _visible_journals(request.user)
    if request.method in SAFE_METHODS:
        entry = get_object_or_404(
            JournalEntry, journal__in=journals, journal_id=journal_pk, pk=entry_pk,
        )
        return Response(JournalEntrySerializer(entry).data)

    with transaction.atomic():
        journal = get_object_or_404(journals.select_for_update(), pk=journal_pk)
        entry = get_object_or_404(JournalEntry, journal=journal, pk=entry_pk)
        require_journal_owner(request, journal)
        if request.method == 'DELETE':
            entry.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = JournalEntrySerializer(entry, data=request.data, partial=request.method == 'PATCH')
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@api_view(['POST', 'DELETE'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def journal_like(request, pk):
    with transaction.atomic():
        journal = get_object_or_404(_visible_journals(request.user).select_for_update(), pk=pk)
        liked = request.method == 'POST'
        if liked:
            journal.likes.get_or_create(user=request.user)
        else:
            journal.likes.filter(user=request.user).delete()
        return Response({'liked': liked, 'likes_count': journal.likes.count()})
