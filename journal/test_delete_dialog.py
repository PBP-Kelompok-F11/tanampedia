from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import JournalEntry, JournalLike, PlantJournal


class JournalDeleteDialogTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='delete-owner')
        self.other = get_user_model().objects.create_user(username='delete-other')
        self.journal = PlantJournal.objects.create(user=self.owner, plant_name='Cabai', is_public=True)
        self.entry = JournalEntry.objects.create(journal=self.journal, header='Daun baru', content='Tumbuh', plant_condition='sehat')
        self.client.force_login(self.owner)

    def entry_url(self):
        return reverse('journal:delete_entry', args=[self.journal.pk, self.entry.pk])

    def journal_url(self):
        return reverse('journal:delete', args=[self.journal.pk])

    def test_detail_has_owner_modal_and_delete_actions(self):
        response = self.client.get(reverse('journal:show_journal_detail', args=[self.journal.pk]))
        self.assertContains(response, '<dialog id="journal-delete-dialog"')
        self.assertContains(response, 'data-delete-kind="journal"')
        self.assertContains(response, 'data-delete-kind="entry"')
        self.assertContains(response, f'data-delete-url="{self.entry_url()}"')
        self.assertNotContains(response, f'href="{reverse("journal:delete_page", args=[self.journal.pk])}"')
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_non_owner_has_no_delete_controls(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse('journal:show_journal_detail', args=[self.journal.pk]))
        self.assertNotContains(response, 'data-delete-trigger')
        self.assertNotContains(response, '<dialog')

    def test_entry_ajax_delete_returns_updated_count_and_preserves_other_data(self):
        other_entry = JournalEntry.objects.create(journal=self.journal, header='Lainnya', content='Lain', plant_condition='sehat')
        response = self.client.post(self.entry_url(), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'deleted': str(self.entry.pk), 'entry_count': 1})
        self.assertTrue(JournalEntry.objects.filter(pk=other_entry.pk).exists())
        self.assertTrue(PlantJournal.objects.filter(pk=self.journal.pk).exists())

    def test_journal_ajax_delete_removes_related_data(self):
        JournalLike.objects.create(journal=self.journal, user=self.other)
        response = self.client.post(self.journal_url(), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['url'], reverse('journal:show_journal_list'))
        self.assertFalse(PlantJournal.objects.filter(pk=self.journal.pk).exists())
        self.assertFalse(JournalEntry.objects.filter(pk=self.entry.pk).exists())
        self.assertFalse(JournalLike.objects.exists())

    def test_ajax_delete_requires_owner(self):
        self.client.force_login(self.other)
        for public in (True, False):
            self.journal.is_public = public
            self.journal.save()
            for url in (self.journal_url(), self.entry_url()):
                self.assertEqual(self.client.post(url, HTTP_ACCEPT='application/json').status_code, 404)
        self.assertTrue(JournalEntry.objects.filter(pk=self.entry.pk).exists())

    def test_csrf_and_authentication_are_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for url in (self.journal_url(), self.entry_url()):
            self.assertEqual(client.post(url, HTTP_ACCEPT='application/json').status_code, 403)
        response = client.get(reverse('journal:show_journal_detail', args=[self.journal.pk]))
        token = response.cookies['csrftoken'].value
        response = client.post(self.entry_url(), HTTP_ACCEPT='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['entry_count'], 0)
        self.client.logout()
        self.assertEqual(self.client.post(self.journal_url(), HTTP_ACCEPT='application/json').status_code, 302)

    def test_get_does_not_delete_and_normal_post_still_redirects(self):
        self.assertEqual(self.client.get(self.journal_url()).status_code, 405)
        self.assertEqual(self.client.get(self.entry_url()).status_code, 200)
        self.assertTrue(JournalEntry.objects.filter(pk=self.entry.pk).exists())
        response = self.client.post(self.entry_url())
        self.assertRedirects(response, reverse('journal:show_journal_detail', args=[self.journal.pk]))
