"""Journal/entry CRUD, authentication, and object-level authorization."""

from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
from unittest.mock import patch

from django.conf import settings
from django.shortcuts import resolve_url
from django.test import Client, TestCase
from django.utils.html import escape

from .models import JournalEntry, JournalLike, PlantJournal
from .test_utils import (
    JournalFixturesMixin, entry_data, journal_data, journal_url, make_entry, make_journal,
)

class JournalCrudTests(JournalFixturesMixin, TestCase):
    def test_create_page_uses_current_status_choices_and_profile_context(self):
        response = self.client.get(journal_url('create_journal_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'journal/create.html')
        self.assertEqual(response.context['status_default_value'], PlantJournal.Status.ACTIVE)
        self.assertEqual(response.context['pedia_points'], self.points())
        self.assertEqual([item['value'] for item in response.context['status_options']], PlantJournal.Status.values)
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_create_assigns_owner_persists_fields_renders_card_and_rewards_once(self):
        points = self.points()
        before = set(PlantJournal.objects.values_list('pk', flat=True))
        response = self.client.post(journal_url('create_journal'), journal_data(is_public='on'))
        self.assertEqual(response.status_code, 201)
        journal = PlantJournal.objects.exclude(pk__in=before).get()
        self.assertEqual(journal.user, self.owner)
        for field, value in journal_data().items():
            self.assertEqual(getattr(journal, field), value)
        self.assertTrue(journal.is_public)
        data = response.json()
        self.assertEqual(data['url'], journal_url('show_journal_detail', journal.pk))
        self.assertIn(journal_url('show_journal_detail', journal.pk), data['html'])
        self.assertIn('journal-card', data['html'])
        self.assertEqual(data['pedia_points'], points + 20)
        self.assertEqual(data['level_title'], self.owner.profile.level['title'])
        self.assertEqual(self.points(), points + 20)

    def test_create_accepts_minimum_fields_and_defaults_to_private(self):
        response = self.client.post(journal_url('create_journal'), {'plant_name': 'Tomat baru', 'status': 'aktif'})
        self.assertEqual(response.status_code, 201)
        journal = PlantJournal.objects.get(plant_name='Tomat baru')
        self.assertFalse(journal.is_public)
        self.assertEqual(journal.thumbnail, '')

    def test_invalid_create_does_not_create_or_reward(self):
        count, points = PlantJournal.objects.count(), self.points()
        for changes, errors in (
            ({'plant_name': ''}, {'plant_name': 'required'}),
            ({'status': ''}, {'status': 'required'}),
            ({'status': 'unknown'}, {'status': 'invalid_choice'}),
            ({'thumbnail': 'not a URL'}, {'thumbnail': 'invalid'}),
            ({'plant_name': 'x' * 201}, {'plant_name': 'max_length'}),
        ):
            with self.subTest(changes=changes):
                response = self.client.post(journal_url('create_journal'), journal_data(**changes))
                self.assert_json_errors(response, **errors)
                self.assertEqual(PlantJournal.objects.count(), count)
                self.assertEqual(self.points(), points)

    def test_create_ignores_submitted_owner_primary_key_and_creation_date(self):
        response = self.client.post(journal_url('create_journal'), journal_data(
            plant_name='Owned by requester', user=self.other.pk, user_id=self.other.pk,
            id=str(self.other_public.pk), start_date='1900-01-01',
        ))
        self.assertEqual(response.status_code, 201)
        journal = PlantJournal.objects.get(plant_name='Owned by requester')
        self.assertEqual(journal.user_id, self.owner.pk)
        self.assertNotEqual(journal.pk, self.other_public.pk)
        self.assertNotEqual(journal.start_date.isoformat(), '1900-01-01')
        self.other_public.refresh_from_db()
        self.assertEqual(self.other_public.plant_name, 'Publik pengguna lain')

    def test_detail_visibility_matrix(self):
        for user in (self.owner, self.other):
            self.client.force_login(user)
            for journal in (self.journal, self.public, self.other_public, self.other_private):
                with self.subTest(user=user.username, journal=journal.plant_name):
                    allowed = journal.is_public or journal.user_id == user.pk
                    response = self.client.get(journal_url('show_journal_detail', journal.pk))
                    self.assertEqual(response.status_code, 200 if allowed else 404)
                    if allowed:
                        self.assertTemplateUsed(response, 'journal/detail.html')
                        self.assertEqual(response.context['journal'].pk, journal.pk)
                        self.assertContains(response, journal.plant_name)

    def test_detail_uses_thumbnail_entries_and_chronological_order(self):
        earlier = make_entry(self.journal, header='Sebelumnya')
        JournalEntry.objects.filter(pk=earlier.pk).update(created_at=self.entry.created_at - timedelta(days=1))
        response = self.client.get(journal_url('show_journal_detail', self.journal.pk))
        self.assertEqual([entry.pk for entry in response.context['entries']], [earlier.pk, self.entry.pk])
        self.assertEqual(response.context['entry_count'], 2)
        self.assertEqual(response.context['cover_image'], self.journal.thumbnail)

    def test_owner_can_load_edit_form_and_change_all_editable_fields(self):
        url = journal_url('edit_journal', self.journal.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'journal/create.html')
        self.assertEqual(response.context['journal_form'].instance.pk, self.journal.pk)
        self.assertEqual(response.context['status_default_value'], self.journal.status)
        before_date, points = self.journal.start_date, self.points()
        data = journal_data(
            plant_name='Panen cabai', description='Selesai', growing_medium='Cocopeat',
            location='Teras', status='panen', thumbnail='https://images.example.test/new.jpg', is_public='on',
        )
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'url': journal_url('show_journal_detail', self.journal.pk)})
        self.journal.refresh_from_db()
        for field in journal_data():
            self.assertEqual(getattr(self.journal, field), data[field])
        self.assertTrue(self.journal.is_public)
        self.assertEqual(self.journal.start_date, before_date)
        self.assertEqual(self.points(), points)

    def test_edit_can_clear_optional_fields_and_make_journal_private(self):
        response = self.client.post(journal_url('edit_journal', self.public.pk), {
            'plant_name': 'Pribadi sekarang', 'status': 'gagal',
        })
        self.assertEqual(response.status_code, 200)
        self.public.refresh_from_db()
        self.assertFalse(self.public.is_public)
        for field in ('description', 'thumbnail', 'growing_medium', 'location'):
            self.assertEqual(getattr(self.public, field), '')

    def test_invalid_edit_leaves_existing_record_and_points_unchanged(self):
        original_name, points = self.journal.plant_name, self.points()
        response = self.client.post(journal_url('edit_journal', self.journal.pk), journal_data(plant_name='', status='unknown'))
        self.assert_json_errors(response, plant_name='required', status='invalid_choice')
        self.journal.refresh_from_db()
        self.assertEqual(self.journal.plant_name, original_name)
        self.assertEqual(self.journal.status, PlantJournal.Status.ACTIVE)
        self.assertEqual(self.points(), points)

    def test_edit_ignores_attempt_to_transfer_owner_or_change_identifier(self):
        response = self.client.post(journal_url('edit_journal', self.journal.pk), journal_data(
            user=self.other.pk, user_id=self.other.pk, id=str(self.other_public.pk), start_date='1900-01-01',
        ))
        self.assertEqual(response.status_code, 200)
        self.journal.refresh_from_db()
        self.assertEqual(self.journal.user_id, self.owner.pk)
        self.assertNotEqual(self.journal.start_date.isoformat(), '1900-01-01')
        self.other_public.refresh_from_db()
        self.assertEqual(self.other_public.user_id, self.other.pk)

    def test_nonowners_cannot_edit_or_delete_even_public_journals(self):
        self.client.force_login(self.other)
        for journal in (self.journal, self.public):
            for name, method in (('edit_journal', 'get'), ('edit_journal', 'post'),
                                 ('delete_page', 'get'), ('delete', 'post')):
                with self.subTest(journal=journal.pk, endpoint=name, method=method):
                    response = getattr(self.client, method)(journal_url(name, journal.pk), journal_data())
                    self.assertEqual(response.status_code, 404)
                    self.assertTrue(PlantJournal.objects.filter(pk=journal.pk, user=self.owner).exists())

    def test_delete_confirmation_is_safe_and_normal_delete_redirects(self):
        response = self.client.get(journal_url('delete_page', self.journal.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'journal/delete.html')
        self.assertTrue(PlantJournal.objects.filter(pk=self.journal.pk).exists())
        points = self.points()
        response = self.client.post(journal_url('delete', self.journal.pk))
        self.assertRedirects(response, journal_url('show_journal_list'))
        self.assertFalse(PlantJournal.objects.filter(pk=self.journal.pk).exists())
        self.assertTrue(PlantJournal.objects.filter(pk=self.public.pk).exists())
        self.assertEqual(self.points(), points)

    def test_failed_response_render_rolls_back_creation_and_reward(self):
        count, points = PlantJournal.objects.count(), self.points()
        with patch('journal.views.render', side_effect=RuntimeError('Rendering failed')):
            with self.assertRaisesMessage(RuntimeError, 'Rendering failed'):
                self.client.post(journal_url('create_journal'), journal_data())
        self.assertEqual(PlantJournal.objects.count(), count)
        self.assertEqual(self.points(), points)

class JournalEntryCrudTests(JournalFixturesMixin, TestCase):
    def test_owner_create_page_contains_form_and_available_conditions(self):
        response = self.client.get(journal_url('create_entry_page', self.journal.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'journal/entry_create.html')
        self.assertEqual(response.context['journal'].pk, self.journal.pk)
        self.assertEqual([item['value'] for item in response.context['condition_options']], JournalEntry.PlantCondition.values)
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_entry_create_persists_data_returns_fragment_and_rewards(self):
        points = self.points()
        before = set(JournalEntry.objects.values_list('pk', flat=True))
        response = self.client.post(journal_url('create_entry', self.journal.pk), entry_data())
        self.assertEqual(response.status_code, 201)
        entry = JournalEntry.objects.exclude(pk__in=before).get()
        self.assertEqual(entry.journal_id, self.journal.pk)
        for field, value in entry_data().items():
            self.assertEqual(getattr(entry, field), value)
        self.assertIn(f'id="entry-{entry.pk}"', response.json()['html'])
        self.assertEqual(response.json()['url'], journal_url('show_journal_detail', self.journal.pk))
        self.assertEqual(response.json()['pedia_points'], points + 5)
        self.assertEqual(self.points(), points + 5)

    def test_invalid_entry_create_neither_saves_nor_rewards(self):
        count, points = JournalEntry.objects.count(), self.points()
        cases = (
            ({'header': ''}, {'header': 'required'}),
            ({'content': ''}, {'content': 'required'}),
            ({'plant_condition': 'unknown'}, {'plant_condition': 'invalid_choice'}),
            ({'image': 'not a URL'}, {'image': 'invalid'}),
        )
        for changes, errors in cases:
            with self.subTest(changes=changes):
                response = self.client.post(journal_url('create_entry', self.journal.pk), entry_data(**changes))
                self.assert_json_errors(response, **errors)
                self.assertEqual(JournalEntry.objects.count(), count)
                self.assertEqual(self.points(), points)

    def test_entry_create_uses_url_parent_and_ignores_extra_identifiers(self):
        response = self.client.post(journal_url('create_entry', self.journal.pk), entry_data(
            header='Bound to URL', journal=str(self.other_public.pk), user=self.other.pk,
            id=str(self.other_entry.pk), created_at='1900-01-01T00:00:00Z',
        ))
        self.assertEqual(response.status_code, 201)
        entry = JournalEntry.objects.get(header='Bound to URL')
        self.assertEqual(entry.journal_id, self.journal.pk)
        self.assertNotEqual(entry.pk, self.other_entry.pk)
        self.assertNotEqual(entry.created_at.year, 1900)

    def test_owner_edit_page_is_populated_and_edit_preserves_parent_date_and_points(self):
        url = journal_url('edit_entry', self.journal.pk, self.entry.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'journal/entry_create.html')
        self.assertEqual(response.context['entry_form'].instance.pk, self.entry.pk)
        self.assertEqual(response.context['condition_value'], self.entry.plant_condition)
        created_at, points = self.entry.created_at, self.points()
        data = entry_data(header='Layu', content='Perlu air', plant_condition='layu', image='')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['url'], journal_url('show_journal_detail', self.journal.pk))
        self.entry.refresh_from_db()
        for field, value in data.items():
            self.assertEqual(getattr(self.entry, field), value)
        self.assertEqual(self.entry.journal_id, self.journal.pk)
        self.assertEqual(self.entry.created_at, created_at)
        self.assertEqual(self.points(), points)

    def test_entry_edit_cannot_reassign_parent_identifier_or_creation_time(self):
        response = self.client.post(journal_url('edit_entry', self.journal.pk, self.entry.pk), entry_data(
            journal=str(self.other_public.pk), id=str(self.other_entry.pk), created_at='1900-01-01T00:00:00Z',
        ))
        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.journal_id, self.journal.pk)
        self.assertNotEqual(self.entry.created_at.year, 1900)
        self.assertTrue(JournalEntry.objects.filter(pk=self.other_entry.pk, journal=self.other_public).exists())

    def test_invalid_entry_edit_preserves_existing_data(self):
        original = self.entry.content
        response = self.client.post(journal_url('edit_entry', self.journal.pk, self.entry.pk), entry_data(content='', image='bad'))
        self.assert_json_errors(response, content='required', image='invalid')
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.content, original)

    def test_nonowners_cannot_manage_entries_even_when_parent_is_public(self):
        entry = make_entry(self.public)
        points = self.points(self.other)
        self.client.force_login(self.other)
        for journal, child in ((self.journal, self.entry), (self.public, entry)):
            cases = (
                ('create_entry_page', 'get', (journal.pk,)),
                ('create_entry', 'post', (journal.pk,)),
                ('edit_entry', 'get', (journal.pk, child.pk)),
                ('edit_entry', 'post', (journal.pk, child.pk)),
                ('delete_entry', 'get', (journal.pk, child.pk)),
                ('delete_entry', 'post', (journal.pk, child.pk)),
            )
            for name, method, args in cases:
                with self.subTest(endpoint=name, method=method, public=journal.is_public):
                    response = getattr(self.client, method)(journal_url(name, *args), entry_data())
                    self.assertEqual(response.status_code, 404)
                    self.assertTrue(JournalEntry.objects.filter(pk=child.pk).exists())
        self.assertEqual(self.points(self.other), points)

    def test_child_cannot_be_accessed_using_a_different_owned_journal(self):
        for name in ('edit_entry', 'delete_entry'):
            for method in ('get', 'post'):
                response = getattr(self.client, method)(journal_url(name, self.public.pk, self.entry.pk), entry_data())
                self.assertEqual(response.status_code, 404)
        self.assertTrue(JournalEntry.objects.filter(pk=self.entry.pk, journal=self.journal).exists())

    def test_delete_confirmation_and_post_redirect_do_not_remove_parent_or_siblings(self):
        sibling = make_entry(self.journal)
        points = self.points()
        url = journal_url('delete_entry', self.journal.pk, self.entry.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'journal/entry_delete.html')
        self.assertTrue(JournalEntry.objects.filter(pk=self.entry.pk).exists())
        response = self.client.post(url)
        self.assertRedirects(response, journal_url('show_journal_detail', self.journal.pk))
        self.assertFalse(JournalEntry.objects.filter(pk=self.entry.pk).exists())
        self.assertTrue(JournalEntry.objects.filter(pk=sibling.pk).exists())
        self.assertTrue(PlantJournal.objects.filter(pk=self.journal.pk).exists())
        self.assertEqual(self.points(), points)

    def test_failed_entry_fragment_render_rolls_back_entry_and_reward(self):
        count, points = JournalEntry.objects.count(), self.points()
        with patch('journal.views.render', side_effect=RuntimeError('Rendering failed')):
            with self.assertRaisesMessage(RuntimeError, 'Rendering failed'):
                self.client.post(journal_url('create_entry', self.journal.pk), entry_data())
        self.assertEqual(JournalEntry.objects.count(), count)
        self.assertEqual(self.points(), points)

class JournalSecurityTests(JournalFixturesMixin, TestCase):
    def endpoints(self):
        j, e = self.journal.pk, self.entry.pk
        return (
            ('show_journal_list', 'get', ()), ('create_journal_page', 'get', ()),
            ('create_journal', 'post', ()), ('show_journal_detail', 'get', (j,)),
            ('edit_journal', 'get', (j,)), ('edit_journal', 'post', (j,)),
            ('delete_page', 'get', (j,)), ('delete', 'post', (j,)),
            ('create_entry_page', 'get', (j,)), ('create_entry', 'post', (j,)),
            ('edit_entry', 'get', (j, e)), ('edit_entry', 'post', (j, e)),
            ('delete_entry', 'get', (j, e)), ('delete_entry', 'post', (j, e)),
            ('toggle_journal_like', 'post', (j,)),
        )

    def test_every_journal_endpoint_requires_authentication(self):
        self.client.logout()
        before = (PlantJournal.objects.count(), JournalEntry.objects.count(), JournalLike.objects.count())
        for name, method, args in self.endpoints():
            with self.subTest(endpoint=name, method=method):
                url = journal_url(name, *args)
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302)
                location = urlsplit(response['Location'])
                self.assertEqual(location.path, resolve_url(settings.LOGIN_URL))
                self.assertEqual(parse_qs(location.query)['next'], [url])
        self.assertEqual((PlantJournal.objects.count(), JournalEntry.objects.count(), JournalLike.objects.count()), before)

    def test_explicit_method_restrictions_return_405_without_mutation(self):
        cases = (
            ('create_journal', (), ('get', 'put', 'delete')),
            ('create_entry', (self.journal.pk,), ('get', 'put', 'delete')),
            ('toggle_journal_like', (self.journal.pk,), ('get', 'put', 'delete')),
            ('delete', (self.journal.pk,), ('get', 'put', 'delete')),
            ('delete_page', (self.journal.pk,), ('post', 'put', 'delete')),
            ('edit_journal', (self.journal.pk,), ('put', 'delete')),
            ('edit_entry', (self.journal.pk, self.entry.pk), ('put', 'delete')),
            ('delete_entry', (self.journal.pk, self.entry.pk), ('put', 'delete')),
        )
        before = (PlantJournal.objects.count(), JournalEntry.objects.count(), JournalLike.objects.count())
        for name, args, methods in cases:
            for method in methods:
                with self.subTest(endpoint=name, method=method):
                    self.assertEqual(getattr(self.client, method)(journal_url(name, *args)).status_code, 405)
        self.assertEqual((PlantJournal.objects.count(), JournalEntry.objects.count(), JournalLike.objects.count()), before)

    def test_unknown_journal_and_entry_identifiers_return_404(self):
        missing = uuid4()
        cases = (
            ('show_journal_detail', 'get', (missing,)),
            ('edit_journal', 'get', (missing,)), ('edit_journal', 'post', (missing,)),
            ('delete_page', 'get', (missing,)), ('delete', 'post', (missing,)),
            ('create_entry_page', 'get', (missing,)), ('create_entry', 'post', (missing,)),
            ('toggle_journal_like', 'post', (missing,)),
            ('edit_entry', 'get', (self.journal.pk, missing)),
            ('edit_entry', 'post', (self.journal.pk, missing)),
            ('delete_entry', 'get', (self.journal.pk, missing)),
            ('delete_entry', 'post', (self.journal.pk, missing)),
            ('edit_entry', 'get', (missing, self.entry.pk)),
            ('delete_entry', 'post', (missing, self.entry.pk)),
        )
        for name, method, args in cases:
            with self.subTest(endpoint=name, method=method):
                self.assertEqual(getattr(self.client, method)(journal_url(name, *args)).status_code, 404)

    def test_malformed_uuid_paths_do_not_resolve(self):
        for path in ('/journal/not-a-uuid/', '/journal/not-a-uuid/like/',
                     f'/journal/{self.journal.pk}/entries/not-a-uuid/edit/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_all_mutating_endpoints_reject_missing_and_invalid_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        before = (PlantJournal.objects.count(), JournalEntry.objects.count(), JournalLike.objects.count(), self.points())
        for name, method, args in self.endpoints():
            if method != 'post':
                continue
            for headers in ({}, {'HTTP_X_CSRFTOKEN': 'invalid'}):
                with self.subTest(endpoint=name, headers=headers):
                    response = client.post(journal_url(name, *args), {**journal_data(), **entry_data()}, **headers)
                    self.assertEqual(response.status_code, 403)
        self.assertEqual((PlantJournal.objects.count(), JournalEntry.objects.count(), JournalLike.objects.count(), self.points()), before)

    def test_valid_csrf_cookie_and_header_allow_create_edit_and_like(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.get(journal_url('show_journal_list'))
        token = response.cookies['csrftoken'].value
        headers = {'HTTP_X_CSRFTOKEN': token}
        self.assertEqual(client.post(journal_url('create_journal'), journal_data(), **headers).status_code, 201)
        self.assertEqual(client.post(journal_url('edit_entry', self.journal.pk, self.entry.pk), entry_data(), **headers).status_code, 200)
        self.assertEqual(client.post(journal_url('toggle_journal_like', self.journal.pk), **headers).status_code, 200)

    def test_journal_and_entry_text_are_escaped_in_pages_and_fragments(self):
        payload = '<script>alert("journal")</script>'
        self.journal.plant_name = payload
        self.journal.description = payload
        self.journal.save()
        self.entry.header = payload
        self.entry.content = payload
        self.entry.save()
        for url in (journal_url('show_journal_list'), journal_url('show_journal_detail', self.journal.pk)):
            response = self.client.get(url)
            self.assertNotContains(response, payload)
            self.assertContains(response, escape(payload))
        response = self.client.post(journal_url('create_entry', self.journal.pk), entry_data(header=payload, content=payload))
        self.assertEqual(response.status_code, 201)
        self.assertNotIn(payload, response.json()['html'])
        self.assertIn(escape(payload), response.json()['html'])
