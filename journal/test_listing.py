"""Observable list behavior and per-user journal likes."""

from datetime import date
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from .models import JournalLike, PlantJournal
from .test_utils import JournalFixturesMixin, journal_url, make_entry, make_journal

class LinkParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tabs = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'data-journal-tab' in attrs:
            self.tabs.append(parse_qs(urlsplit(attrs['href']).query))

class JournalListingTests(JournalFixturesMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.journal.plant_name = 'Cabai lama'
        cls.journal.description = 'Pertumbuhan pertama'
        cls.journal.save()
        cls.public.plant_name = 'Tomat'
        cls.public.description = 'Percobaan CABAI'
        cls.public.status = 'panen'
        cls.public.save()
        cls.newer = make_journal(cls.owner, plant_name='Cabai baru')
        cls.tied = make_journal(cls.owner, plant_name='Kemangi', status='gagal')
        for journal, day in ((cls.journal, 1), (cls.public, 2), (cls.tied, 3), (cls.newer, 4)):
            journal.start_date = date(2025, 1, day)
            PlantJournal.objects.filter(pk=journal.pk).update(start_date=journal.start_date)
        JournalLike.objects.bulk_create([
            JournalLike(journal=cls.journal, user=cls.other),
            JournalLike(journal=cls.journal, user=cls.third),
            JournalLike(journal=cls.public, user=cls.other),
            JournalLike(journal=cls.tied, user=cls.third),
        ])

    def assert_journals(self, expected, **params):
        response = self.client.get(journal_url('show_journal_list'), params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([journal.pk for journal in response.context['journals']], [journal.pk for journal in expected])
        return response

    def test_default_and_explicit_newest_use_creation_date(self):
        for params in ({}, {'sort': 'newest'}):
            response = self.assert_journals([self.newer, self.tied, self.public, self.journal], **params)
            self.assertEqual(response.context['sort'], 'newest')
            self.assertEqual(response.context['active_tab'], 'my')
            self.assertTemplateUsed(response, 'journal/list.html')

    def test_newest_same_day_ties_use_actual_primary_keys(self):
        PlantJournal.objects.filter(pk=self.public.pk).update(start_date=self.newer.start_date)
        expected = sorted([self.public, self.newer], key=lambda journal: journal.pk, reverse=True)
        self.assert_journals([*expected, self.tied, self.journal])

    def test_most_liked_keeps_zero_likes_and_uses_newest_for_equal_counts(self):
        response = self.assert_journals([self.journal, self.tied, self.public, self.newer], sort='most_liked')
        self.assertEqual([journal.likes_count for journal in response.context['journals']], [2, 1, 1, 0])

    def test_most_liked_same_date_and_count_use_primary_key(self):
        PlantJournal.objects.filter(pk=self.public.pk).update(start_date=self.tied.start_date)
        tied = sorted([self.public, self.tied], key=lambda journal: journal.pk, reverse=True)
        self.assert_journals([self.journal, *tied, self.newer], sort='most_liked')

    def test_invalid_or_empty_sort_falls_back_to_newest(self):
        for sort in ('', 'unknown', '-likes_count', 'MOST_LIKED'):
            with self.subTest(sort=sort):
                response = self.assert_journals([self.newer, self.tied, self.public, self.journal], sort=sort)
                self.assertEqual(response.context['sort'], 'newest')

    def test_searches_name_and_description_case_insensitively_and_trims_query(self):
        response = self.assert_journals([self.newer, self.public, self.journal], q='  cAbAi  ')
        self.assertEqual(response.context['query'], 'cAbAi')
        self.assert_journals([self.tied], q='Kemangi')

    def test_empty_or_whitespace_search_returns_all_and_nonmatch_returns_empty(self):
        for query in ('', '   '):
            self.assert_journals([self.newer, self.tied, self.public, self.journal], q=query)
        response = self.assert_journals([], q='tidak-ada-tanaman-ini')
        self.assertContains(response, 'Tidak ada jurnal yang sesuai dengan pencarian')

    def test_only_supported_search_fields_are_used(self):
        self.assert_journals([], q='Balkon')  # Location is not a search field.

    def test_each_status_can_be_selected(self):
        for status, expected in (
            ('aktif', [self.newer, self.journal]), ('panen', [self.public]), ('gagal', [self.tied]),
        ):
            with self.subTest(status=status):
                response = self.assert_journals(expected, status=status)
                self.assertEqual(response.context['status'], status)

    def test_liked_filter_uses_requesting_users_likes_not_any_like(self):
        for journal in (self.journal, self.newer, self.other_private):
            JournalLike.objects.create(journal=journal, user=self.owner)
        self.assert_journals([self.newer, self.journal], liked='1')
        self.assert_journals([self.journal, self.newer], liked='1', sort='most_liked')

    def test_search_filters_and_sorting_combine_without_changing_like_counts(self):
        for journal in (self.journal, self.newer, self.public):
            JournalLike.objects.create(journal=journal, user=self.owner)
        response = self.assert_journals([self.journal, self.newer], q='cabai', liked='1', status='aktif', sort='most_liked')
        self.assertEqual([journal.likes_count for journal in response.context['journals']], [3, 1])

    def test_for_you_excludes_own_and_private_journals_even_with_a_stored_like(self):
        for journal in (self.other_public, self.other_private, self.public):
            JournalLike.objects.create(journal=journal, user=self.owner)
        for sort in ('newest', 'most_liked'):
            self.assert_journals([self.other_public], tab='for-you', liked='1', sort=sort)
        self.assert_journals([], tab='for-you', q=self.other_private.plant_name)

    def test_invalid_filters_and_tab_fall_back_safely(self):
        for params in (
            {'status': 'unknown', 'liked': 'unknown', 'tab': 'unknown'},
            {'status': '', 'liked': 'true'},
            {'status': 'all', 'liked': 'all'},
        ):
            response = self.assert_journals([self.newer, self.tied, self.public, self.journal], **params)
            self.assertEqual(response.context['status'], 'all')
            self.assertEqual(response.context['liked'], 'all')
            self.assertEqual(response.context['active_tab'], 'my')

    def test_controls_and_tab_links_preserve_query_values_and_reset_page(self):
        response = self.client.get(journal_url('show_journal_list'), {
            'q': 'cabai & tomat', 'sort': 'most_liked', 'liked': '1', 'status': 'panen',
            'tab': 'for-you', 'page': '4', 'tag': ['sayur', 'buah'],
        })
        self.assertEqual(response.context['query'], 'cabai & tomat')
        self.assertEqual(response.context['sort'], 'most_liked')
        self.assertEqual(response.context['liked'], '1')
        self.assertEqual(response.context['status'], 'panen')
        self.assertEqual(response.context['list_query_params'], [('tab', 'for-you'), ('tag', 'sayur'), ('tag', 'buah')])
        self.assertContains(response, 'name="q"', count=1)
        self.assertContains(response, 'value="cabai &amp; tomat"')
        self.assertNotContains(response, 'name="page"')
        tabs = LinkParser(response.content.decode()).tabs
        self.assertEqual(len(tabs), 2)
        for params in tabs:
            self.assertEqual(params['q'], ['cabai & tomat'])
            self.assertEqual(params['sort'], ['most_liked'])
            self.assertEqual(params['tag'], ['sayur', 'buah'])
            self.assertEqual(params['liked'], ['1'])
            self.assertEqual(params['status'], ['panen'])
            self.assertNotIn('page', params)

    def test_listing_uses_thumbnail_and_entry_summaries(self):
        newer_entry = make_entry(self.journal, image='https://images.example.test/latest-entry.jpg')
        response = self.client.get(journal_url('show_journal_list'))
        journal = next(item for item in response.context['journals'] if item.pk == self.journal.pk)
        self.assertEqual(journal.cover_image, self.journal.thumbnail)
        self.assertEqual(journal.entry_count, 2)
        self.assertEqual(journal.last_activity, newer_entry.created_at)
        empty = next(item for item in response.context['journals'] if item.pk == self.newer.pk)
        self.assertEqual(empty.entry_count, 0)
        self.assertIsNone(empty.last_activity)

    def test_query_count_does_not_grow_with_authors_entries_and_likes(self):
        url = journal_url('show_journal_list')
        with CaptureQueriesContext(connection) as baseline:
            self.client.get(url, {'tab': 'for-you', 'sort': 'most_liked'})
        for index in range(8):
            journal = make_journal(self.third, plant_name=f'Tanaman {index}', is_public=True)
            for entry in range(3):
                make_entry(journal, header=f'Entri {entry}')
            JournalLike.objects.create(journal=journal, user=self.owner)
        with CaptureQueriesContext(connection) as expanded:
            response = self.client.get(url, {'tab': 'for-you', 'sort': 'most_liked'})
        self.assertEqual(len(response.context['journals']), 9)
        self.assertEqual(len(expanded), len(baseline))

    def test_empty_my_and_filtered_for_you_states_render(self):
        PlantJournal.objects.filter(user=self.owner).delete()
        response = self.assert_journals([])
        self.assertContains(response, 'Belum ada jurnal.')
        response = self.assert_journals([], tab='for-you', status='panen')
        self.assertContains(response, 'Tidak ada jurnal yang sesuai dengan filter')
        self.other_public.delete()
        response = self.assert_journals([], tab='for-you')
        self.assertContains(response, 'Belum ada jurnal publik')

class JournalLikeTests(JournalFixturesMixin, TestCase):
    def test_like_and_unlike_toggle_rows_and_json_state_without_awarding_points(self):
        url = journal_url('toggle_journal_like', self.other_public.pk)
        points = self.points()
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'liked': True, 'likes_count': 1})
        self.assertTrue(JournalLike.objects.filter(journal=self.other_public, user=self.owner).exists())
        response = self.client.post(url)
        self.assertEqual(response.json(), {'liked': False, 'likes_count': 0})
        self.assertFalse(JournalLike.objects.filter(journal=self.other_public, user=self.owner).exists())
        self.assertEqual(self.points(), points)

    def test_toggle_preserves_other_users_likes_and_reports_total(self):
        JournalLike.objects.create(journal=self.public, user=self.other)
        JournalLike.objects.create(journal=self.public, user=self.third)
        url = journal_url('toggle_journal_like', self.public.pk)
        self.assertEqual(self.client.post(url).json(), {'liked': True, 'likes_count': 3})
        self.assertEqual(self.client.post(url).json(), {'liked': False, 'likes_count': 2})
        self.assertCountEqual(self.public.likes.values_list('user_id', flat=True), [self.other.pk, self.third.pk])

    def test_owner_may_like_a_private_journal_but_nonowner_cannot(self):
        url = journal_url('toggle_journal_like', self.journal.pk)
        self.assertEqual(self.client.post(url).json(), {'liked': True, 'likes_count': 1})
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.journal.likes.count(), 1)

    def test_posted_user_and_journal_values_cannot_spoof_the_like_target(self):
        response = self.client.post(journal_url('toggle_journal_like', self.public.pk), {
            'user': self.other.pk, 'user_id': self.other.pk, 'journal': str(self.other_private.pk),
        })
        self.assertEqual(response.json(), {'liked': True, 'likes_count': 1})
        self.assertTrue(JournalLike.objects.filter(journal=self.public, user=self.owner).exists())
        self.assertFalse(JournalLike.objects.filter(user=self.other).exists())
        self.assertFalse(self.other_private.likes.exists())

    def test_like_state_and_count_are_reflected_in_list_and_detail_for_each_user(self):
        JournalLike.objects.create(journal=self.public, user=self.owner)
        for user, liked in ((self.owner, True), (self.other, False)):
            self.client.force_login(user)
            detail = self.client.get(journal_url('show_journal_detail', self.public.pk))
            self.assertEqual(detail.context['journal'].likes_count, 1)
            self.assertEqual(detail.context['journal'].is_liked, liked)
            self.assertContains(detail, f'aria-pressed="{str(liked).lower()}"')
            self.assertContains(detail, '1 likes')
            tab = 'my' if user == self.owner else 'for-you'
            listing = self.client.get(journal_url('show_journal_list'), {'tab': tab})
            journal = next(item for item in listing.context['journals'] if item.pk == self.public.pk)
            self.assertEqual(journal.likes_count, 1)
            self.assertEqual(journal.is_liked, liked)

    def test_preexisting_like_does_not_grant_access_after_journal_becomes_private(self):
        JournalLike.objects.create(journal=self.other_public, user=self.owner)
        self.other_public.is_public = False
        self.other_public.save()
        response = self.client.post(journal_url('toggle_journal_like', self.other_public.pk))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(JournalLike.objects.filter(journal=self.other_public, user=self.owner).exists())
