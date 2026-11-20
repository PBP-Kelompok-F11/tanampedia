"""Seed the database with demo data for all core features.

Satisfies the "minimum 50 records of core data" deployment requirement:
seeds 60 users, 60 plant journals (with entries), 60 forum questions
(with answers), and ~68 quiz questions - every category clears 50 on
its own.

Run order matters (users -> journal -> forum -> quiz) since journal and
forum entries belong to seeded users, and quiz questions are attributed
to one. Usage:

    python manage.py seed_data
    python manage.py seed_data --flush   # wipe previously seeded data first
"""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from forum.models import Answer, Question as ForumQuestion
from journal.models import JournalEntry, JournalLike, PlantJournal
from quiz.models import AnswerOption, Question as QuizQuestion

User = get_user_model()

SEED_PREFIX = 'seed_user_'
SEED_PASSWORD = 'TanamSeed#2026'

USER_COUNT = 60
JOURNAL_COUNT = 60
FORUM_QUESTION_COUNT = 60

FIRST_NAMES = [
    'Budi', 'Siti', 'Andi', 'Dewi', 'Rizky', 'Putri', 'Agus', 'Rina',
    'Hendra', 'Maya', 'Fajar', 'Lestari', 'Dian', 'Wulan', 'Yusuf',
    'Indah', 'Bayu', 'Citra', 'Eko', 'Nadia', 'Fitri', 'Gilang',
    'Hana', 'Ivan', 'Kartika',
]
LAST_NAMES = [
    'Santoso', 'Wijaya', 'Kurnia', 'Pratama', 'Hidayat', 'Saputra',
    'Permadi', 'Utami', 'Nugroho', 'Setiawan', 'Rahayu', 'Gunawan',
    'Puspita', 'Anggraini', 'Maulana', 'Wibowo', 'Halim', 'Susanti',
    'Firmansyah', 'Oktaviani',
]

BIO_TEMPLATES = [
    'Suka berkebun urban di waktu luang, lagi belajar hidroponik.',
    'Pekebun rumahan, fokus ke tanaman sayur dan bumbu dapur.',
    'Baru mulai hobi berkebun tahun ini, masih banyak belajar.',
    'Penggemar tanaman hias dan sayuran organik.',
    'Petani kota yang percaya semua orang bisa berkebun di lahan sempit.',
    'Suka eksperimen media tanam, dari sekam sampai cocopeat.',
    'Berkebun sambil healing, panen hasil tani sendiri itu puas banget.',
    'Mencoba konsisten nanam sayur buat kebutuhan dapur sendiri.',
]

PLANT_FACTS = {
    'Cabai Rawit': {'germinasi': '7-14 hari', 'media': 'tanah gembur campur kompos', 'siram': '1 kali sehari', 'hama': 'kutu daun'},
    'Tomat': {'germinasi': '5-10 hari', 'media': 'tanah subur dan gembur', 'siram': '1 kali sehari', 'hama': 'ulat buah tomat'},
    'Selada': {'germinasi': '2-6 hari', 'media': 'hidroponik atau tanah gembur', 'siram': '2 kali sehari', 'hama': 'kutu daun'},
    'Bayam': {'germinasi': '5-7 hari', 'media': 'tanah gembur berdrainase baik', 'siram': '1 kali sehari', 'hama': 'ulat grayak'},
    'Kangkung': {'germinasi': '3-5 hari', 'media': 'tanah lembap atau air', 'siram': '2 kali sehari', 'hama': 'kutu daun'},
    'Terong': {'germinasi': '7-14 hari', 'media': 'tanah gembur dengan pupuk kandang', 'siram': '1 kali sehari', 'hama': 'kumbang daun'},
    'Timun': {'germinasi': '6-10 hari', 'media': 'tanah gembur dan subur', 'siram': '1 kali sehari', 'hama': 'lalat buah'},
    'Kemangi': {'germinasi': '5-10 hari', 'media': 'tanah gembur dengan sinar cukup', 'siram': '1 kali sehari', 'hama': 'kutu daun'},
    'Sawi': {'germinasi': '3-5 hari', 'media': 'tanah gembur dan subur', 'siram': '2 kali sehari', 'hama': 'ulat daun'},
    'Jahe': {'germinasi': '14-21 hari', 'media': 'tanah gembur dan lembap', 'siram': '1 kali sehari', 'hama': 'kutu putih'},
    'Kunyit': {'germinasi': '14-21 hari', 'media': 'tanah gembur dengan naungan sebagian', 'siram': '1 kali sehari', 'hama': 'ulat tanah'},
    'Serai': {'germinasi': None, 'media': 'tanah gembur berdrainase baik', 'siram': '1 kali sehari', 'hama': 'jarang terserang hama'},
    'Pepaya': {'germinasi': '14-21 hari', 'media': 'tanah gembur dengan drainase baik', 'siram': '1 kali sehari', 'hama': 'kutu putih'},
    'Lidah Buaya': {'germinasi': None, 'media': 'tanah berpasir dengan drainase baik', 'siram': '1 kali seminggu', 'hama': 'kutu putih'},
    'Stroberi': {'germinasi': '14-21 hari', 'media': 'tanah gembur kaya humus', 'siram': '1 kali sehari', 'hama': 'kutu daun'},
    'Kacang Panjang': {'germinasi': '4-7 hari', 'media': 'tanah gembur dan subur', 'siram': '1 kali sehari', 'hama': 'kutu kebul'},
    'Bawang Merah': {'germinasi': '5-10 hari', 'media': 'tanah gembur berpasir', 'siram': '1 kali sehari', 'hama': 'ulat bawang'},
    'Pandan': {'germinasi': None, 'media': 'tanah lembap dengan naungan sebagian', 'siram': '1 kali sehari', 'hama': 'jarang terserang hama'},
}
PLANT_NAMES = list(PLANT_FACTS.keys())

GROWING_MEDIA = [
    'Tanah', 'Tanah humus', 'Cocopeat', 'Hidroponik sistem NFT',
    'Hidroponik sistem wick', 'Sekam bakar', 'Campuran kompos', 'Pot dengan sekam',
]
LOCATIONS = [
    'Balkon apartemen Depok', 'Halaman rumah Bandung', 'Rooftop Jakarta Selatan',
    'Pekarangan Bogor', 'Teras rumah Tangerang', 'Kebun belakang Yogyakarta',
    'Balkon rumah Surabaya', 'Halaman samping Bekasi', 'Lahan kosong Malang',
    'Pot gantung Semarang',
]
STATUS_WEIGHTS = [
    (PlantJournal.Status.ACTIVE, 60),
    (PlantJournal.Status.HARVESTED, 30),
    (PlantJournal.Status.FAILED, 10),
]

JOURNAL_DESCRIPTION_TEMPLATES = [
    'Mulai menanam {plant} di {location} menggunakan media {medium}. Semoga hasilnya memuaskan!',
    'Journal perkembangan {plant} saya, ditanam dengan {medium} di {location}.',
    'Eksperimen menanam {plant} pertama kali pakai {medium}. Progres dicatat di sini.',
    'Journal ini mencatat proses tanam {plant} dari bibit hingga panen di {location}.',
    'Nyobain nanam {plant} di {location}, media {medium}. Semoga nggak gagal panen.',
    'Catatan harian merawat {plant} dengan media {medium} di {location}.',
]

ENTRY_CONTENT_TEMPLATES = {
    JournalEntry.PlantCondition.HEALTHY: [
        'Daun {plant} terlihat segar dan hijau, pertumbuhan stabil minggu ini.',
        'Batang {plant} semakin kokoh, belum ada tanda hama.',
        '{plant} tumbuh subur, akar tampak kuat waktu dicek.',
        'Penyiraman rutin bikin {plant} tumbuh lebih cepat dari minggu lalu.',
    ],
    JournalEntry.PlantCondition.WILTED: [
        'Beberapa daun {plant} mulai layu, kemungkinan kurang air atau terlalu banyak sinar matahari.',
        '{plant} terlihat kurang segar, mungkin perlu pindah lokasi yang lebih teduh.',
        'Pertumbuhan {plant} melambat, ada daun yang mulai menguning dan layu.',
    ],
    JournalEntry.PlantCondition.DEAD: [
        'Sayangnya {plant} tidak bertahan, kemungkinan akibat akar busuk.',
        '{plant} mati setelah beberapa hari layu, akan coba tanam ulang dengan media berbeda.',
    ],
}
ENTRY_CONDITION_WEIGHTS = [
    (JournalEntry.PlantCondition.HEALTHY, 70),
    (JournalEntry.PlantCondition.WILTED, 22),
    (JournalEntry.PlantCondition.DEAD, 8),
]

FORUM_SYMPTOMS = [
    'daunnya menguning', 'layu meski rutin disiram', 'muncul bercak coklat di daun',
    'pertumbuhannya sangat lambat', 'diserang kutu putih', 'batangnya membusuk',
    'tidak kunjung berbunga', 'daunnya berlubang-lubang', 'akarnya mulai busuk',
    'warna daunnya memucat',
]
FORUM_QUESTION_TEMPLATES = [
    'Kenapa {plant} saya {symptom}? Ada yang tahu solusinya?',
    'Tanaman {plant} di rumah {symptom}, ini normal atau bahaya ya?',
    'Butuh saran: {plant} saya {symptom} sejak minggu lalu.',
    'Apakah {plant} yang {symptom} masih bisa diselamatkan?',
]
FORUM_ANSWER_TEMPLATES = [
    'Coba cek drainase pot {plant} kamu, bisa jadi akarnya kelebihan air.',
    'Biasanya itu tanda kekurangan nutrisi, coba kasih pupuk organik untuk {plant}.',
    'Kurangi paparan sinar matahari langsung dulu, {plant} mungkin stres panas.',
    'Itu gejala umum serangan hama, coba semprot pestisida organik di {plant}.',
    'Pastikan medianya tidak terlalu padat, akar {plant} butuh ruang bernapas.',
    'Saya pernah alami ini juga di {plant} saya, ternyata kurang sinar matahari.',
]

QUIZ_TEMPLATES = [
    ('germinasi', 'Berapa rata-rata waktu perkecambahan biji {plant}?'),
    ('media', 'Media tanam apa yang paling cocok untuk {plant}?'),
    ('siram', 'Idealnya, tanaman {plant} disiram berapa kali sehari/seminggu?'),
    ('hama', 'Apa hama yang umum menyerang tanaman {plant}?'),
]

# Some fact types (especially "siram") only have a handful of distinct real
# values across all plants in PLANT_FACTS, which isn't always enough to fill
# 3 distractor slots once the correct answer is excluded. These pad the pool
# out - still plausible-sounding, just not necessarily any other plant's
# actual fact.
GENERIC_DISTRACTORS = {
    'germinasi': ['1-2 hari', '30-45 hari', '2-3 bulan'],
    'media': ['pasir murni tanpa campuran', 'air murni tanpa nutrisi', 'kerikil kasar'],
    'siram': ['3 kali sehari', '2 kali seminggu', '1 kali per dua hari', '1 kali sebulan'],
    'hama': ['tidak ada hama yang diketahui', 'rayap tanah', 'siput'],
}


def weighted_choice(pairs):
    options, weights = zip(*pairs)
    return random.choices(options, weights=weights, k=1)[0]


class Command(BaseCommand):
    help = 'Seed demo data for users, journals, forum Q&A, and quiz questions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='Delete previously seeded data (identified by the seed_user_ username prefix) before seeding.',
        )

    def handle(self, *args, **options):
        if options['flush']:
            self._flush()
        elif User.objects.filter(username__startswith=SEED_PREFIX).exists():
            raise CommandError(
                'Seed data already exists. Re-run with --flush to replace it.'
            )

        with transaction.atomic():
            users = self._seed_users()
            journals = self._seed_journals(users)
            questions = self._seed_forum(users)
            quiz_questions = self._seed_quiz(users)

        self.stdout.write(self.style.SUCCESS(
            f'\nSeeded {len(users)} users, {len(journals)} journals, '
            f'{len(questions)} forum questions, {len(quiz_questions)} quiz questions.'
        ))
        self.stdout.write(f'All seeded accounts share the password: {SEED_PASSWORD}')

    def _flush(self):
        quiz_deleted, _ = QuizQuestion.objects.filter(
            created_by__username__startswith=SEED_PREFIX
        ).delete()
        user_deleted, _ = User.objects.filter(username__startswith=SEED_PREFIX).delete()
        self.stdout.write(f'Flushed previous seed data ({user_deleted} related rows).')

    # -- Users ----------------------------------------------------------

    def _seed_users(self):
        self.stdout.write('Seeding users...')
        name_pairs = random.sample(
            [(first, last) for first in FIRST_NAMES for last in LAST_NAMES], USER_COUNT
        )
        users = []
        now = timezone.now()
        for i in range(1, USER_COUNT + 1):
            first, last = name_pairs[i - 1]
            username = f'{SEED_PREFIX}{i:02d}'
            joined = now - timedelta(days=random.randint(1, 365))
            user = User.objects.create_user(
                username=username,
                email=f'{username}@tanampedia.test',
                password=SEED_PASSWORD,
                date_joined=joined,
            )
            points = random.randint(4000, 9000) if i <= 6 else random.randint(0, 4000)
            profile = user.profile
            profile.display_name = f'{first} {last}'
            profile.bio = random.choice(BIO_TEMPLATES)
            profile.profile_picture_url = f'https://i.pravatar.cc/300?img={(i % 70) + 1}'
            profile.pedia_points = points
            profile.save()
            users.append(user)
        return users

    # -- Journal ----------------------------------------------------------

    def _seed_journals(self, users):
        self.stdout.write('Seeding plant journals...')
        journals = []
        for i in range(1, JOURNAL_COUNT + 1):
            plant = random.choice(PLANT_NAMES)
            medium = random.choice(GROWING_MEDIA)
            location = random.choice(LOCATIONS)
            status = weighted_choice(STATUS_WEIGHTS)
            user = random.choice(users)

            journal = PlantJournal.objects.create(
                user=user,
                plant_name=plant,
                description=random.choice(JOURNAL_DESCRIPTION_TEMPLATES).format(
                    plant=plant, medium=medium, location=location,
                ),
                growing_medium=medium,
                location=location,
                status=status,
                is_public=random.random() < 0.8,
                thumbnail=f'https://picsum.photos/seed/tanampedia-journal-{i}/640/420',
            )
            # start_date is auto_now_add - backdate it after creation so the
            # feed/leaderboard don't look like everything was planted today.
            backdated = timezone.now().date() - timedelta(days=random.randint(1, 180))
            PlantJournal.objects.filter(pk=journal.pk).update(start_date=backdated)
            journal.start_date = backdated
            journals.append(journal)

            for entry_index in range(1, random.randint(1, 3) + 1):
                condition = weighted_choice(ENTRY_CONDITION_WEIGHTS)
                JournalEntry.objects.create(
                    journal=journal,
                    content=random.choice(ENTRY_CONTENT_TEMPLATES[condition]).format(plant=plant),
                    image=f'https://picsum.photos/seed/tanampedia-entry-{i}-{entry_index}/640/420',
                    plant_condition=condition,
                )

            if journal.is_public:
                likers = random.sample(users, k=random.randint(0, min(15, len(users) - 1)))
                JournalLike.objects.bulk_create([
                    JournalLike(journal=journal, user=liker)
                    for liker in likers if liker != user
                ], ignore_conflicts=True)

        return journals

    # -- Forum ----------------------------------------------------------

    def _seed_forum(self, users):
        self.stdout.write('Seeding forum Q&A...')
        questions = []
        for _ in range(FORUM_QUESTION_COUNT):
            plant = random.choice(PLANT_NAMES)
            symptom = random.choice(FORUM_SYMPTOMS)
            author = random.choice(users)
            question = ForumQuestion.objects.create(
                author=author,
                title=random.choice(FORUM_QUESTION_TEMPLATES).format(plant=plant, symptom=symptom),
                content=(
                    f'Halo semua, tanaman {plant} saya {symptom}. '
                    'Sudah coba beberapa cara tapi belum membaik. Ada saran?'
                ),
            )
            questions.append(question)

            answerers = random.sample(users, k=min(random.randint(1, 4), len(users)))
            for answerer in answerers:
                if answerer == author:
                    continue
                answer = Answer.objects.create(
                    question=question,
                    author=answerer,
                    content=random.choice(FORUM_ANSWER_TEMPLATES).format(plant=plant),
                )
                upvoters = random.sample(users, k=random.randint(0, 10))
                answer.upvotes.set(upvoters)

        return questions

    # -- Quiz ----------------------------------------------------------

    def _seed_quiz(self, users):
        self.stdout.write('Seeding quiz questions...')
        created_by_pool = users[:10]
        questions = []

        for plant, facts in PLANT_FACTS.items():
            for fact_key, prompt_template in QUIZ_TEMPLATES:
                correct_value = facts[fact_key]
                if correct_value is None:
                    continue

                distractor_pool = {
                    other_facts[fact_key]
                    for other_plant, other_facts in PLANT_FACTS.items()
                    if other_plant != plant and other_facts[fact_key]
                }
                distractor_pool |= set(GENERIC_DISTRACTORS[fact_key])
                # Other plants can coincidentally share the same fact value
                # (e.g. most plants are watered "1 kali sehari") - exclude it
                # explicitly so it can never double up as both a distractor
                # and the correct option on the same question.
                distractor_pool.discard(correct_value)
                distractors = random.sample(list(distractor_pool), 3)

                question = QuizQuestion.objects.create(
                    prompt=prompt_template.format(plant=plant),
                    explanation=f'{plant} idealnya: {correct_value}.',
                    is_active=True,
                    created_by=random.choice(created_by_pool),
                )

                options = distractors + [correct_value]
                random.shuffle(options)
                for position, text in enumerate(options, start=1):
                    AnswerOption.objects.create(
                        question=question,
                        position=position,
                        text=text,
                        is_correct=(text == correct_value),
                    )
                questions.append(question)

        return questions
