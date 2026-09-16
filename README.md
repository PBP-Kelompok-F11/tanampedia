<h1 align="center">Tanampedia</h1>

<p align="center">
  <a href="https://www.djangoproject.com/"><img alt="django" src="https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white" /></a>
  <a href="https://www.python.org"><img alt="html" src="https://img.shields.io/badge/HTML5-E34F26?style=flat&logo=html5&logoColor=white" /></a>
  <a href="https://www.python.org"><img alt="css" src="https://img.shields.io/badge/-CSS-1572B6?style=flat-square&logo=css&logoColor=white" /></a>
  <a href="https://www.python.org"><img alt="django" src="https://shields.io/badge/JavaScript-F7DF1E?logo=JavaScript&logoColor=white&style=flat" /></a>
</p>

<p align="center">
    <strong>Kelas</strong> PBP F | <strong>Kelompok</strong> 11
</p>

### Anggota

| NPM        | Nama                           |
| ---------- | ------------------------------ |
| 2506551125 | Ervhino Aryo Seto              |
| 2506596041 | Forza Derian                   |
| 2506584861 | Mohammad Zidane Kurnianto      |
| 2506588752 | Muhammad Fairus Azfar Arisandi |
| 2506602896 | Muhammad Naufal Syarifuddin    |

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

> **Made with 😹 by PBP-F11**
