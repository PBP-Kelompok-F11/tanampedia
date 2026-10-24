from django.conf import settings
from django.db import models


class Profile(models.Model):
    EXPERIENCE_CHOICES = [
        ('pemula', 'Pemula'),
        ('berpengalaman', 'Berpengalaman'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    experience_level = models.CharField(
        max_length=20,
        choices=EXPERIENCE_CHOICES,
        default='pemula',
    )
    pedia_points = models.PositiveIntegerField(default=0)
    bio = models.TextField(blank=True)

    def __str__(self):
        return f'{self.user.username} profile'
