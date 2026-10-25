# Standar Penggunaan App Accounts

App lain dependen terhadap app accounts, jadi hati-hati ya guys, jangan sampai salah... 😹

## Mengakses Profile User

Setiap `User` otomatis punya `Profile` terkait (dibuat lewat signal saat register — manual maupun lewat Google OAuth nanti), jadi tinggal akses `user.profile` langsung, tidak perlu query/import `Profile` di app lain:

```python
request.user.profile.pedia_points                # int, default 0
request.user.profile.display_name_or_username     # fallback ke username kalau display_name kosong
request.user.profile.level                         # dict: {'threshold', 'title', 'description'}
request.user.profile.profile_picture_url           # string kosong kalau belum diisi user
```

## Menambahkan PediaPoints dari Modul Lain

Semua modul di atas (Forum, Katalog, Kuis, Journal) memberi PediaPoints ke user di titik tertentu (upvote, jawaban benar, like, dst). Untuk itu, **selalu pakai `profile.add_points(jumlah)`**, jangan `profile.pedia_points += jumlah; profile.save()` secara manual — cara manual itu rawan race condition (poin bisa hilang kalau dua request datang bersamaan, misal dua upvote hampir bersamaan).

```python
# Contoh: kasih 10 poin ke penjawab forum saat jawabannya di-upvote
answer.author.profile.add_points(10)

# Jumlah negatif juga bisa (misal upvote dibatalkan) — otomatis di-clamp di angka 0
answer.author.profile.add_points(-10)
```

Detail implementasinya ada di `accounts/models.py` (`Profile.add_points`).

## URL yang Mungkin Kepakai

Buat nge-link ke halaman auth dari app lain (misal "Login dulu buat jawab" di Forum):

```django
{% url 'account_login' %}      {# halaman login #}
{% url 'account_signup' %}     {# halaman daftar #}
{% url 'accounts:profile' %}   {# profil user yang lagi login #}
```

Kalau view-nya butuh user login dulu, tinggal pakai `@login_required` biasa — otomatis redirect ke halaman login di atas.
