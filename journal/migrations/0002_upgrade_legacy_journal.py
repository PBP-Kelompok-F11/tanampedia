"""Upgrade the integer-ID schema already applied on the production server.

Run during a maintenance window: object IDs change and old integer URLs expire.
The conversion is intentionally irreversible; retain a database backup.
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models


def populate_uuid(apps, schema_editor):
    alias = schema_editor.connection.alias
    Journal = apps.get_model('journal', 'PlantJournal')
    Entry = apps.get_model('journal', 'JournalEntry')
    Like = apps.get_model('journal', 'JournalLike')
    for journal in Journal.objects.using(alias).all().iterator():
        new_id = uuid.uuid4()
        Journal.objects.using(alias).filter(pk=journal.pk).update(uuid_id=new_id)
        Entry.objects.using(alias).filter(journal_id=journal.pk).update(journal_uuid=new_id)
        Like.objects.using(alias).filter(journal_id=journal.pk).update(journal_uuid=new_id)
    for entry in Entry.objects.using(alias).all().iterator():
        Entry.objects.using(alias).filter(pk=entry.pk).update(uuid_id=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [('journal', '0001_initial')]

    operations = [
        migrations.AddField('plantjournal', 'uuid_id', models.UUIDField(null=True)),
        migrations.AddField('journalentry', 'uuid_id', models.UUIDField(null=True)),
        migrations.AddField('journalentry', 'journal_uuid', models.UUIDField(null=True)),
        migrations.AddField('journallike', 'journal_uuid', models.UUIDField(null=True)),
        migrations.RunPython(populate_uuid),
        migrations.RemoveConstraint('journallike', 'unique_journal_like_per_user'),
        migrations.RemoveField('journalentry', 'journal'),
        migrations.RemoveField('journallike', 'journal'),
        migrations.RemoveField('plantjournal', 'id'),
        migrations.AlterField('plantjournal', 'uuid_id', models.UUIDField(
            primary_key=True, default=uuid.uuid4, editable=False, serialize=False,
        )),
        migrations.RenameField('plantjournal', 'uuid_id', 'id'),
        migrations.AlterField('journalentry', 'journal_uuid', models.ForeignKey(
            to='journal.plantjournal', related_name='entries', on_delete=django.db.models.deletion.CASCADE,
        )),
        migrations.AlterField('journallike', 'journal_uuid', models.ForeignKey(
            to='journal.plantjournal', related_name='likes', on_delete=django.db.models.deletion.CASCADE,
        )),
        migrations.RenameField('journalentry', 'journal_uuid', 'journal'),
        migrations.RenameField('journallike', 'journal_uuid', 'journal'),
        migrations.RemoveField('journalentry', 'id'),
        migrations.AlterField('journalentry', 'uuid_id', models.UUIDField(
            primary_key=True, default=uuid.uuid4, editable=False, serialize=False,
        )),
        migrations.RenameField('journalentry', 'uuid_id', 'id'),
        migrations.AddConstraint('journallike', models.UniqueConstraint(
            fields=('journal', 'user'), name='unique_journal_like_per_user',
        )),
        migrations.AddField('plantjournal', 'growing_medium', models.CharField(max_length=200, blank=True)),
        migrations.AddField('plantjournal', 'location', models.CharField(max_length=200, blank=True)),
        migrations.AddField('plantjournal', 'thumbnail', models.URLField(blank=True)),
    ]
