from django.conf import settings


def google_oauth_enabled(request):
    return {
        'google_oauth_enabled': bool(
            settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET
        ),
    }
