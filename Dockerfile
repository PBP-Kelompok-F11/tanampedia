# Debian-based (glibc), not Alpine — psycopg2-binary, cryptography (needed by
# PyJWT[crypto] for Google OAuth), etc. all ship prebuilt manylinux wheels for
# glibc, so pip never needs to compile anything from source. Alpine (musl)
# lacks those wheels, forcing a slow from-source build that was blowing past
# PWS's build timeout.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Tailwind's compiled CSS is already committed by the GitHub Actions deploy
# workflow before this ever reaches PWS, so this just gathers existing static
# files into STATIC_ROOT for whitenoise — no Node/Tailwind CLI needed here.
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Deliberately NOT running `migrate` here — it used to block this CMD before
# gunicorn could open the port, which may be why PWS's health check marked
# the container unhealthy (Bad Gateway) despite the app eventually booting
# fine. Run migrations manually via the PWS Terminal tab after deploying:
#   python manage.py migrate --noinput
CMD ["sh", "-c", "gunicorn tanampedia.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
