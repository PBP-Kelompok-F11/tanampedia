import uuid

from django.conf import settings
from django.db import models


class PlantJournal(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'aktif', 'Aktif'
        HARVESTED = 'panen', 'Panen'
        FAILED = 'gagal', 'Gagal'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='plant_journals',
    )
    plant_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    growing_medium = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    start_date = models.DateField(auto_now_add=True)
    is_public = models.BooleanField(default=False)
    thumbnail = models.URLField(blank=True)

    class Meta:
        ordering = ('-start_date', '-pk')

    def __str__(self):
        return self.plant_name


class JournalLike(models.Model):
    journal = models.ForeignKey(
        PlantJournal,
        on_delete=models.CASCADE,
        related_name='likes',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='journal_likes',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('journal', 'user'),
                name='unique_journal_like_per_user',
            ),
        ]
        ordering = ('created_at', 'pk')

    def __str__(self):
        return f'{self.user} likes {self.journal}'


class JournalEntry(models.Model):
    class PlantCondition(models.TextChoices):
        HEALTHY = 'sehat', 'Sehat'
        WILTED = 'layu', 'Layu'
        DEAD = 'mati', 'Mati'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal = models.ForeignKey(
        PlantJournal,
        on_delete=models.CASCADE,
        related_name='entries',
    )
    content = models.TextField()
    image = models.URLField(blank=True)
    plant_condition = models.CharField(
        max_length=10,
        choices=PlantCondition.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'pk')

    def __str__(self):
        return f'{self.journal.plant_name} - {self.get_plant_condition_display()}'
