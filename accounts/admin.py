from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level_title', 'pedia_points')
    search_fields = ('user__username', 'user__email')

    @admin.display(description='Level')
    def level_title(self, obj):
        return obj.level['title']
