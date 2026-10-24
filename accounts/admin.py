from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'experience_level', 'pedia_points')
    list_filter = ('experience_level',)
    search_fields = ('user__username', 'user__email')
