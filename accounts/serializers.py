from django.utils.html import strip_tags
from rest_framework import serializers

from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    level = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id", "username", "display_name", "bio", "profile_picture_url",
            "pedia_points", "level",
        ]
        read_only_fields = ["id", "pedia_points"]

    def get_level(self, obj):
        return obj.level["title"]

    def validate_display_name(self, value):
        return strip_tags(value).strip()

    def validate_bio(self, value):
        return strip_tags(value)
