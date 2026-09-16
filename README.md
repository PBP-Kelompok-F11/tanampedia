<h1 align="center">Tanampedia</h1>

<p align="center">
  <a href="https://www.djangoproject.com/"><img alt="django" src="https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white" /></a>
  <a href="https://www.python.org"><img alt="html" src="https://img.shields.io/badge/HTML5-E34F26?style=flat&logo=html5&logoColor=white" /></a>
  <a href="https://www.python.org"><img alt="css" src="https://img.shields.io/badge/-CSS-1572B6?style=flat-square&logo=css&logoColor=white" /></a>
  <a href="https://www.python.org"><img alt="django" src="https://shields.io/badge/JavaScript-F7DF1E?logo=JavaScript&logoColor=white&style=flat" /></a>
  <a href="https://sqlite.org"><img alt="postgresql" src="https://img.shields.io/badge/postgresql-4169e1?style=flat&logo=postgresql&logoColor=white" /></a>
</p>

Kelas : PBP F

Kelompok : 11

Anggota :

- Ervhino Aryo Seto (2506551125)
- Forza Derian (2506596041)
- Mohammad Zidane Kurnianto (2506584861)
- Muhammad Fairus Azfar Arisandi (2506588752)
- Muhammad Naufal Syarifuddin (2506602896)

## Deskripsi

Aplikasi ini adalah **platform komunitas yang menghubungkan petani atau pekebun dengan petani lainnya untuk saling berbagi pengetahuan**. Melalui ruang diskusi interaktif, katalog referensi tanaman yang terverifikasi (dari API Trefle), platform ini merangkum informasi urban farming yang tadinya tersebar menjadi satu platform yang praktis. Aplikasi ini bertujuan memudahkan siapa saja untuk memulai berkebun skala kecil dan berkontribusi pada gaya hidup yang lebih berkelanjutan.

## Features (Modules)

1. Authentication: mulai dari proses register, log-in, log-out, dan profil yang menampilkan pengalaman dan pediapoints **(Zika)**
2. Q&A Forum -> user posting masalah, komunitas menjawab, user lain yang merasa terbantu oleh sebuah jawaban bisa meng-upvote jawaban tersebut. Setiap upvote pada sebuah jawaban, user mendapatkan pediapoint **(Naufal)**
3. Katalog tanaman -> database referensi, lengkap dengan detail cara menanam dan merawat **(Ervhino)**
4. Kuis dan Challenge Harian -> modul kecil berisi kuis singkat seputar dasar bertani (multiple choice), user dapat poin kalau jawab benar, menambah pediapoint yang udah ada, dan bikin proses belajar lebih interaktif dibanding cuma baca forum/katalog **(Forza)**
5. User Journal and Posting -> user bisa post image dan caption ke publik, publik bisa like dan user yang ngepost bisa dapat pediapoint setiap like **(Fairuz)**

## API yang akan Digunakan

1. [Trefle](https://trefle.io/), sebagai sumber data referensi perawatan tanaman
2. [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2?hl=id), sebagai sumber data referensi perawatan tanaman

## User Persona

1. Petani/Pekebun Pemula: bisa berupa petani muda dan pekebun yang tertarik untuk belajar dan bertanya di forum
2. Petani/Pekebun Berpengalaman: menjawab dan membangun reputasi
3. Admin: moderasi konten dan mengelola data tanaman referensi
