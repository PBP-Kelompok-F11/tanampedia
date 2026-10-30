<h1 align="center">Tanampedia</h1>
<h6 align="center">Tumbuh Bersama, Hijaukan Halaman</h6>

<p align="center">
  <a href="https://www.djangoproject.com/"><img alt="django" src="https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white" /></a>
  <a href="https://www.python.org"><img alt="html" src="https://img.shields.io/badge/HTML5-E34F26?style=flat&logo=html5&logoColor=white" /></a>
  <a href="https://www.python.org"><img alt="css" src="https://img.shields.io/badge/-CSS-1572B6?style=flat-square&logo=css&logoColor=white" /></a>
  <a href="https://www.python.org"><img alt="django" src="https://shields.io/badge/JavaScript-F7DF1E?logo=JavaScript&logoColor=white&style=flat" /></a>
  <a href="https://tailwindcss.com/"><img alt="tailwindcss" src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat&logo=tailwindcss&logoColor=white" /></a>
</p>

<p align="center">
    <strong>Kelas</strong> PBP F | <strong>Kelompok</strong> 11
</p>

### Anggota

| | NPM | Nama | Jurusan | Role |
| :-: | --- | --- | --- | --- |
| <img src="https://github.com/ervhinoaryoseto-del.png" width="64" alt="Ervhino Aryo Seto"> | 2506551125 | **Ervhino Aryo Seto** | Information Systems '25 @ Universitas Indonesia | Katalog Tanaman |
| <img src="https://github.com/voruzaa.png" width="64" alt="Forza Derian"> | 2506596041 | **Forza Derian** | Information Systems '25 @ Universitas Indonesia | Kuis & Challenge Harian |
| <img src="https://github.com/zikabyte.png" width="64" alt="Mohammad Zidane Kurnianto"> | 2506584861 | **Mohammad Zidane Kurnianto** | Information Systems '25 @ Universitas Indonesia | Authentication, Profile, & Leaderboard |
| <img src="https://github.com/fairusarisandi.png" width="64" alt="Muhammad Fairus Azfar Arisandi"> | 2506588752 | **Muhammad Fairus Azfar Arisandi** | Information Systems '25 @ Universitas Indonesia | User Journal & Posting |
| <img src="https://github.com/Roatsky.png" width="64" alt="Muhammad Naufal Syarifuddin"> | 2506602896 | **Muhammad Naufal Syarifuddin** | Information Systems '25 @ Universitas Indonesia | Q&A Forum |

## Deskripsi

**Tanampedia** adalah platform edukasi dan sharing berbasis komunitas yang menghubungkan petani/pekebun dengan petani/pekebun lainnya untuk saling berbagi pengetahuan. Platform ini secara khusus menargetkan petani muda, yang cenderung lebih menikmati proses belajar yang interaktif dan gamified dibanding metode belajar konvensional. Melalui ruang diskusi interaktif, katalog referensi tanaman yang terverifikasi, platform ini merangkum informasi urban farming yang tadinya tersebar menjadi satu platform yang praktis. Aplikasi ini bertujuan memudahkan siapa saja untuk memulai berkebun skala kecil dan berkontribusi pada gaya hidup yang lebih berkelanjutan.

## Fitur (Modules)

1. **Authentication:** Mengelola proses register, login, dan logout pengguna, serta halaman profil yang menampilkan pengalaman dan PediaPoints (yaitu poin yang dikumpulkan dari keaktifan user dalam beraktivitas di platform). Berencana untuk memakai OAuth (Google) untuk kemudahan login dan disertai fallback login/register manual **_(Mohammad Zidane Kurnianto)_**.
2. **Q&A Forum:** Ruang diskusi tempat user mengunggah pertanyaan seputar bertani. User yang merasa terbantu oleh suatu jawaban bisa upvote, dan setiap upvote yang diterima memberi PediaPoint ke penjawab **_(Muhammad Naufal Syarifuddin)_**.
3. **Katalog tanaman:** Database referensi tanaman lengkap dengan detail cara menanam dan merawat (kebutuhan cahaya, air, suhu, dll), diambil dari Trefle API, supaya user punya sumber panduan yang bisa diandalkan **_(Ervhino Aryo Seto)_**.
4. **Kuis dan Challenge Harian:** Modul kuis singkat (_multiple choice_) seputar dasar-dasar bertani yang diadakan sekali sehari. Setiap jawaban benar memberi PediaPoint, menciptakan suasana belajar yang lebih interaktif dan "pemuda-friendly" **_(Forza Derian)_**.
5. User Journal and Posting: User bisa mengunggah foto beserta caption ke publik (misal progres kebun, hasil panen, momen bertani) yang bisa dilihat dan di-like user lain. Setiap like yang diterima juga memberi PediaPoint ke pemilik post **_(Muhammad Fairus Azfar Arisandi)_**.

## API yang akan Digunakan

1. [Trefle](https://trefle.io/), sebagai sumber data referensi perawatan tanaman.
2. [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2?hl=id), memungkinkan user aplikasi Tanampedia masuk menggunakan akun Google.

## User Persona

1. **Petani/Pekebun Pemula:** Amatir, terutama petani muda dan pekebun, yang tertarik mendalami dunia pertanian lebih lanjut
2. **Petani/Pekebun Berpengalaman:** Berpengalaman dalam dunia pertanian, menjawab dan membangun koleksi PediaPoint
3. **Admin:** Moderasi konten dan mengelola data

## Dependencies

| Package | Versi | Kegunaan |
| --- | --- | --- |
| [Django](https://www.djangoproject.com/) | 5.2.17 | Web framework utama. |
| [django-allauth](https://docs.allauth.org/) | 65.20.1 | Login dengan Google OAuth (login/register manual pakai auth bawaan Django sendiri). |
| [django-tailwind](https://django-tailwind.readthedocs.io/) | 4.6.0 | Integrasi Tailwind CSS ke dalam Django. |
| [pytailwindcss](https://github.com/timonweb/pytailwindcss) | 0.4.2 | Mengunduh & menjalankan Tailwind CLI tanpa perlu install Node.js. |
| [whitenoise](https://whitenoise.readthedocs.io/) | 6.12.0 | Serve static files langsung dari Django, tanpa web server terpisah. |
| [gunicorn](https://gunicorn.org/) | 26.2.0 | WSGI HTTP server untuk deployment production. |
| [psycopg2-binary](https://www.psycopg.org/) | 2.9.13 | Driver PostgreSQL untuk database production. |
| [PyJWT](https://pyjwt.readthedocs.io/)[crypto] | 2.15.1 | Verifikasi token, dipakai `django-allauth` untuk Google OAuth. |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.2.4 | Memuat environment variable dari file `.env`. |
| [requests](https://requests.readthedocs.io/) | 2.32.3 | HTTP client, dipakai untuk memanggil Trefle API (Katalog Tanaman). |
| [asgiref](https://github.com/django/asgiref) | 3.12.1 | Utilitas ASGI/WSGI, dependency internal Django. |
| [sqlparse](https://github.com/andialbrecht/sqlparse) | 0.6.0 | Parsing SQL, dependency internal Django (migrations, admin). |
| [tzdata](https://pypi.org/project/tzdata/) | 2026.4 | Database timezone, dibutuhkan di sistem (mis. Windows) yang tidak punya tz database bawaan OS. |
| [coverage](https://coverage.readthedocs.io/) | 7.17.0 | Mengukur code coverage dari test suite. |

## Essential Links

| Name       | Link                           |
| ---------- | ------------------------------ |
| Figma Design | https://www.figma.com/design/THxw4O2FNxy30dOkLS9P72/TanamPedia--PBP-F-11-?node-id=0-1&t=jWu86prW4uvzR0tt-1              |
| Deployment | https://muhammad-fairus51-tanampedia.pws.cs.ui.ac.id/ |
| AI Disclosure | [docs/AI.md](docs/AI.md) |

## Get Started

Panduan untuk menjalankan proyek ini secara lokal.

### Requirements

- Python 3.13
- Git

### 1. Clone repository

```bash
git clone https://github.com/PBP-Kelompok-F11/tanampedia.git
cd tanampedia
```

### 2. Buat & aktifkan virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Siapkan environment variables

Salin `.env.example` menjadi `.env`, lalu isi sesuai kebutuhan:

```bash
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env
```

| Variable | Wajib? | Keterangan |
| --- | --- | --- |
| `PRODUCTION` | Tidak | Biarkan `False` untuk lokal - otomatis pakai SQLite, tidak perlu setup database terpisah. |
| `SECRET_KEY` | Disarankan | Generate dengan `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Tidak | Opsional, dari [Google Cloud Console](https://console.cloud.google.com/). Tanpa ini, login/register manual tetap jalan normal, tombol "Lanjutkan dengan Google" otomatis tersembunyi. |
| `TREFLE_API_TOKEN` | Tidak | Opsional, dari [Trefle](https://trefle.io/). Tanpa ini, halaman Katalog Tanaman tetap tampil dengan fallback ke pesan "belum dikonfigurasi". |

### 5. Jalankan migrasi database

```bash
python manage.py migrate
```

### 6. (Opsional) Buat akun admin

```bash
python manage.py createsuperuser
```

### 7. (Opsional) Isi data demo

Mengisi database dengan data dummy (user, journal, forum, kuis) supaya aplikasi tidak terasa kosong saat dicoba:

```bash
python manage.py seed_data
```

Semua akun hasil seed memakai password yang sama, dicetak di akhir perintah di atas.

### 8. Jalankan development server

```bash
python manage.py runserver
```

Buka [http://127.0.0.1:8000/](http://127.0.0.1:8000/) di browser.

> CSS Tailwind yang sudah di-*build* sudah ikut ter-*commit* di repo, jadi langkah di atas saja sudah cukup. Kalau mau mengubah styling Tailwind dan melihat perubahannya secara *live*, jalankan `python manage.py tailwind start` di terminal terpisah.

### Menjalankan Test

```bash
python manage.py test
```

Atau sekalian dengan laporan *code coverage*:

```bash
coverage run manage.py test
coverage report        # ringkasan di terminal
coverage html          # laporan HTML di htmlcov/index.html
```

> **Made with 😹 by PBP-F11**
