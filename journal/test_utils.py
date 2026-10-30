"""Small fixtures shared by the journal integration tests."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import JournalEntry, PlantJournal


def journal_url(name, *args):
    return reverse(f'journal:{name}', args=args)


def journal_data(**overrides):
    data = {
        'plant_name': 'Cabai rawit',
        'description': 'Catatan pertumbuhan tanaman.',
        'growing_medium': 'Tanah',
        'location': 'Balkon',
        'status': PlantJournal.Status.ACTIVE,
        'thumbnail': 'https://images.example.test/cover.jpg',
    }
    data.update(overrides)
    return data


def entry_data(**overrides):
    data = {
        'header': 'Daun baru',
        'content': 'Tanaman mulai tumbuh.',
        'plant_condition': JournalEntry.PlantCondition.HEALTHY,
        'image': 'https://images.example.test/entry.jpg',
    }
    data.update(overrides)
    return data


def make_journal(user, **overrides):
    return PlantJournal.objects.create(user=user, **journal_data(**overrides))


def make_entry(journal, **overrides):
    return JournalEntry.objects.create(journal=journal, **entry_data(**overrides))


class JournalFixturesMixin:
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        users = get_user_model().objects
        cls.owner = users.create_user(username='journal-owner')
        cls.other = users.create_user(username='journal-other')
        cls.third = users.create_user(username='journal-third')
        cls.journal = make_journal(cls.owner, plant_name='Jurnal pribadi')
        cls.public = make_journal(cls.owner, plant_name='Jurnal publik', is_public=True)
        cls.other_public = make_journal(cls.other, plant_name='Publik pengguna lain', is_public=True)
        cls.other_private = make_journal(cls.other, plant_name='Pribadi pengguna lain')
        cls.entry = make_entry(cls.journal)
        cls.other_entry = make_entry(cls.other_public)

    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        # Image fields contain URLs. CRUD must neither download images nor
        # upload/delete files; make an unexpected external interaction fail.
        for target in (
            'requests.sessions.Session.request',
            'urllib.request.urlopen',
            'django.core.files.storage.FileSystemStorage.save',
            'django.core.files.storage.FileSystemStorage.delete',
        ):
            patcher = patch(target, side_effect=AssertionError(f'Unexpected I/O: {target}'))
            mocked = patcher.start()
            self.addCleanup(patcher.stop)
            self.addCleanup(mocked.assert_not_called)

    def points(self, user=None):
        profile = (user or self.owner).profile
        profile.refresh_from_db()
        return profile.pedia_points

    def assert_json_errors(self, response, **codes):
        self.assertEqual(response.status_code, 400)
        errors = response.json()['errors']
        for field, code in codes.items():
            self.assertIn(code, [error['code'] for error in errors[field]])
