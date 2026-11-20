"""Model and form contracts; HTTP behavior lives in test_views/test_listing."""

from datetime import date, timedelta
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .forms import JournalEntryForm, PlantJournalForm
from .models import JournalEntry, JournalLike, PlantJournal
from .test_utils import entry_data, journal_data, make_entry, make_journal


class JournalModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username='model-owner')
        cls.other = get_user_model().objects.create_user(username='model-other')
        cls.journal = make_journal(cls.owner)
        cls.entry = make_entry(cls.journal)

    def test_minimal_journal_defaults_and_generated_identifier(self):
        journal = PlantJournal.objects.create(user=self.owner, plant_name='Tomat')
        journal.full_clean()
        self.assertIsInstance(journal.pk, UUID)
        self.assertEqual(journal.pk.version, 4)
        self.assertNotEqual(journal.pk, self.journal.pk)
        self.assertIsInstance(journal.start_date, date)
        self.assertEqual(journal.status, PlantJournal.Status.ACTIVE)
        self.assertFalse(journal.is_public)
        for field in ('description', 'growing_medium', 'location', 'thumbnail'):
            self.assertEqual(getattr(journal, field), '')

    def test_creation_date_is_not_reset_on_update(self):
        original = self.journal.start_date
        self.journal.plant_name = 'Cabai merah'
        self.journal.save()
        self.journal.refresh_from_db()
        self.assertEqual(self.journal.start_date, original)

    def test_required_journal_fields_and_invalid_status_fail_full_clean(self):
        cases = (
            ({'plant_name': ''}, 'plant_name', 'blank'),
            ({'plant_name': 'x' * 201}, 'plant_name', 'max_length'),
            ({'user': None}, 'user', 'null'),
            ({'status': 'unknown'}, 'status', 'invalid_choice'),
            ({'thumbnail': 'javascript:alert(1)'}, 'thumbnail', 'invalid'),
        )
        for changes, field, code in cases:
            with self.subTest(field=field, code=code):
                journal = PlantJournal(user=self.owner, **journal_data())
                for name, value in changes.items():
                    setattr(journal, name, value)
                with self.assertRaises(ValidationError) as caught:
                    journal.full_clean()
                self.assertIn(code, [error.code for error in caught.exception.error_dict[field]])

    def test_all_declared_statuses_validate_and_have_display_labels(self):
        for value, label in PlantJournal.Status.choices:
            with self.subTest(status=value):
                self.journal.status = value
                self.journal.full_clean()
                self.assertEqual(self.journal.get_status_display(), label)

    def test_relationships_and_string_representations(self):
        like = JournalLike.objects.create(journal=self.journal, user=self.other)
        self.assertIn(self.journal, self.owner.plant_journals.all())
        self.assertEqual(list(self.journal.entries.all()), [self.entry])
        self.assertEqual(list(self.journal.likes.all()), [like])
        self.assertEqual(list(self.other.journal_likes.all()), [like])
        self.assertEqual(str(self.journal), self.journal.plant_name)
        self.assertEqual(str(self.entry), f'{self.journal.plant_name} - Sehat')
        self.assertEqual(str(like), f'{self.other} likes {self.journal}')

    def test_journal_order_uses_date_then_actual_primary_keys(self):
        same_day = make_journal(self.owner)
        older = make_journal(self.owner)
        PlantJournal.objects.filter(pk__in=[self.journal.pk, same_day.pk]).update(start_date=date(2025, 2, 1))
        PlantJournal.objects.filter(pk=older.pk).update(start_date=date(2025, 1, 1))
        tied = sorted([self.journal.pk, same_day.pk], reverse=True)
        self.assertEqual(list(PlantJournal.objects.values_list('pk', flat=True)), [*tied, older.pk])

    def test_entry_defaults_identifier_timestamp_and_timestamp_preservation(self):
        entry = JournalEntry.objects.create(
            journal=self.journal, header='Bunga', content='Mulai berbunga', plant_condition='sehat',
        )
        entry.full_clean()
        self.assertIsInstance(entry.pk, UUID)
        self.assertNotEqual(entry.pk, self.entry.pk)
        self.assertEqual(entry.image, '')
        self.assertTrue(timezone.is_aware(entry.created_at))
        created_at = entry.created_at
        entry.content = 'Bunga baru'
        entry.save()
        entry.refresh_from_db()
        self.assertEqual(entry.created_at, created_at)

    def test_entry_required_fields_and_conditions(self):
        for field in ('header', 'content', 'plant_condition'):
            with self.subTest(field=field):
                entry = JournalEntry(journal=self.journal, **entry_data(**{field: ''}))
                with self.assertRaises(ValidationError) as caught:
                    entry.full_clean()
                self.assertIn(field, caught.exception.message_dict)
        entry = JournalEntry(**entry_data())
        with self.assertRaises(ValidationError) as caught:
            entry.full_clean()
        self.assertIn('journal', caught.exception.message_dict)
        self.entry.plant_condition = 'unknown'
        with self.assertRaises(ValidationError):
            self.entry.full_clean()
        for value, label in JournalEntry.PlantCondition.choices:
            self.entry.plant_condition = value
            self.entry.full_clean()
            self.assertEqual(self.entry.get_plant_condition_display(), label)

    def test_deleting_an_entry_preserves_its_journal_likes_and_siblings(self):
        sibling = make_entry(self.journal)
        like = JournalLike.objects.create(journal=self.journal, user=self.other)
        self.entry.delete()
        self.assertTrue(PlantJournal.objects.filter(pk=self.journal.pk).exists())
        self.assertEqual(list(self.journal.entries.all()), [sibling])
        self.assertEqual(list(self.journal.likes.all()), [like])

    def test_entries_are_chronological_with_deterministic_ties(self):
        second = make_entry(self.journal)
        latest = make_entry(self.journal)
        instant = timezone.now() - timedelta(days=2)
        JournalEntry.objects.filter(pk__in=[self.entry.pk, second.pk]).update(created_at=instant)
        JournalEntry.objects.filter(pk=latest.pk).update(created_at=instant + timedelta(days=1))
        expected = [*sorted([self.entry.pk, second.pk]), latest.pk]
        self.assertEqual(list(self.journal.entries.values_list('pk', flat=True)), expected)

    def test_duplicate_like_is_rejected_by_database_without_corrupting_transaction(self):
        JournalLike.objects.create(journal=self.journal, user=self.other)
        with self.assertRaises(IntegrityError), transaction.atomic():
            JournalLike.objects.create(journal=self.journal, user=self.other)
        self.assertEqual(self.journal.likes.count(), 1)
        JournalLike.objects.create(journal=self.journal, user=self.owner)
        other_journal = make_journal(self.owner)
        JournalLike.objects.create(journal=other_journal, user=self.other)
        self.assertEqual(JournalLike.objects.count(), 3)

    def test_deleting_journal_cascades_only_its_entries_and_likes(self):
        keep = make_journal(self.other)
        keep_entry = make_entry(keep)
        keep_like = JournalLike.objects.create(journal=keep, user=self.owner)
        JournalLike.objects.create(journal=self.journal, user=self.other)
        self.journal.delete()
        self.assertFalse(JournalEntry.objects.filter(pk=self.entry.pk).exists())
        self.assertEqual(list(JournalLike.objects.all()), [keep_like])
        self.assertTrue(JournalEntry.objects.filter(pk=keep_entry.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=self.owner.pk).exists())

    def test_deleting_user_cascades_owned_journals_and_their_likes_only(self):
        keep = make_journal(self.other)
        keep_entry = make_entry(keep)
        JournalLike.objects.create(journal=keep, user=self.owner)
        JournalLike.objects.create(journal=self.journal, user=self.other)
        self.owner.delete()
        self.assertFalse(PlantJournal.objects.filter(pk=self.journal.pk).exists())
        self.assertFalse(JournalEntry.objects.filter(pk=self.entry.pk).exists())
        self.assertFalse(JournalLike.objects.exists())
        self.assertTrue(JournalEntry.objects.filter(pk=keep_entry.pk).exists())

    def test_deleting_liker_preserves_another_users_journal(self):
        JournalLike.objects.create(journal=self.journal, user=self.other)
        self.other.delete()
        self.assertTrue(PlantJournal.objects.filter(pk=self.journal.pk).exists())
        self.assertTrue(JournalEntry.objects.filter(pk=self.entry.pk).exists())
        self.assertFalse(self.journal.likes.exists())


class JournalFormTests(SimpleTestCase):
    def test_journal_minimum_data_accepts_optional_fields_as_blank(self):
        form = PlantJournalForm({'plant_name': '  Tomat  ', 'status': 'aktif'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['plant_name'], 'Tomat')
        self.assertFalse(form.cleaned_data['is_public'])
        for field in ('description', 'growing_medium', 'location', 'thumbnail'):
            self.assertEqual(form.cleaned_data[field], '')

    def test_journal_form_required_invalid_and_overlong_fields(self):
        cases = (
            ({'plant_name': ''}, 'plant_name', 'required'),
            ({'plant_name': '   '}, 'plant_name', 'required'),
            ({'status': ''}, 'status', 'required'),
            ({'status': 'unknown'}, 'status', 'invalid_choice'),
            ({'plant_name': 'x' * 201}, 'plant_name', 'max_length'),
            ({'growing_medium': 'x' * 201}, 'growing_medium', 'max_length'),
            ({'location': 'x' * 201}, 'location', 'max_length'),
            ({'thumbnail': 'not a URL'}, 'thumbnail', 'invalid'),
            ({'thumbnail': 'javascript:alert(1)'}, 'thumbnail', 'invalid'),
        )
        for changes, field, code in cases:
            with self.subTest(field=field, code=code):
                form = PlantJournalForm(journal_data(**changes))
                self.assertFalse(form.is_valid())
                self.assertIn(code, [error.code for error in form.errors.as_data()[field]])

    def test_valid_journal_choices_urls_and_public_checkbox(self):
        for status in PlantJournal.Status.values:
            form = PlantJournalForm(journal_data(status=status, is_public='on'))
            self.assertTrue(form.is_valid(), form.errors)
            self.assertTrue(form.cleaned_data['is_public'])
            self.assertEqual(form.cleaned_data['thumbnail'], journal_data()['thumbnail'])

    def test_ownership_and_automatic_fields_are_excluded_from_forms(self):
        for form, excluded in (
            (PlantJournalForm(), ('id', 'user', 'start_date')),
            (JournalEntryForm(), ('id', 'journal', 'created_at')),
        ):
            for field in excluded:
                self.assertNotIn(field, form.fields)

    def test_entry_minimum_data_and_optional_image(self):
        form = JournalEntryForm({'header': '  Bunga  ', 'content': 'Tumbuh', 'plant_condition': 'sehat'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['header'], 'Bunga')
        self.assertEqual(form.cleaned_data['image'], '')

    def test_entry_form_rejects_missing_invalid_and_overlong_data(self):
        cases = (
            ({'header': ''}, 'header', 'required'),
            ({'content': '  '}, 'content', 'required'),
            ({'plant_condition': ''}, 'plant_condition', 'required'),
            ({'plant_condition': 'unknown'}, 'plant_condition', 'invalid_choice'),
            ({'header': 'x' * 201}, 'header', 'max_length'),
            ({'image': 'not a URL'}, 'image', 'invalid'),
            ({'image': 'javascript:alert(1)'}, 'image', 'invalid'),
        )
        for changes, field, code in cases:
            with self.subTest(field=field, code=code):
                form = JournalEntryForm(entry_data(**changes))
                self.assertFalse(form.is_valid())
                self.assertIn(code, [error.code for error in form.errors.as_data()[field]])

    def test_every_declared_entry_condition_accepts_valid_data(self):
        for condition in JournalEntry.PlantCondition.values:
            form = JournalEntryForm(entry_data(plant_condition=condition))
            self.assertTrue(form.is_valid(), form.errors)
