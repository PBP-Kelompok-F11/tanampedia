from django.conf import settings
from django.db import models


class Profile(models.Model):
    LEVELS = [
        {'threshold': 7501, 'title': 'Sultan Lahan', 'description': 'Legenda hidup dunia berkebun, nama Anda akan dikenang di Tanampedia.'},
        {'threshold': 4501, 'title': 'Bos Panen', 'description': 'Setiap panen selalu melimpah, hasil kebunmu jadi bahan bicara satu kota.'},
        {'threshold': 2801, 'title': 'Juragan Bibit', 'description': 'Koleksi bibitmu bikin iri satu RT, orang mulai ngantre minta tips.'},
        {'threshold': 1701, 'title': 'Mandor Kebun', 'description': 'Mulai dipercaya ngatur-ngatur kebun bareng dan kasih arahan ke yang lebih baru.'},
        {'threshold': 1001, 'title': 'Ahli Cangkok', 'description': 'Tanganmu udah lincah nyangkok, sering dimintain tolong tetangga untuk mencangkok.'},
        {'threshold': 601, 'title': 'Pawang Hama', 'description': 'Andalan warga forum kalau ada yang panik tanamannya diserang hama.'},
        {'threshold': 301, 'title': 'Peracik Pupuk', 'description': 'Mulai berani racik pupuk sendiri, walau separuhnya masih untung-untungan.'},
        {'threshold': 151, 'title': 'Sobat Cangkul', 'description': 'Namamu mulai disebut-sebut sama petani sekitar sebagai anak yang rajin turun kebun.'},
        {'threshold': 51, 'title': 'Tukang Siram', 'description': 'Udah hafal jadwal nyiram sendiri, walau nama-nama tanamannya masih suka ketuker.'},
        {'threshold': 0, 'title': 'Petani Magang', 'description': 'Masih beradaptasi memegang sekop dan menyimak obrolan senior.'},
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    pedia_points = models.PositiveIntegerField(default=0)
    bio = models.TextField(blank=True)

    def __str__(self):
        return f'{self.user.username} profile'

    @property
    def level(self):
        for lvl in self.LEVELS:
            if self.pedia_points >= lvl['threshold']:
                return lvl
        return self.LEVELS[-1]
