from django.contrib.auth import get_user_model
from django.utils.html import strip_tags
from rest_framework import serializers

from forum.models import Question, Answer

User = get_user_model()

class AuthorSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "name"]

    def get_name(self, obj):
        profile = getattr(obj, "profile", None)
        if profile and hasattr(profile, "display_name_or_username"):
            return profile.display_name_or_username
        return obj.username

class QuestionSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    class Meta:
        model = Question
        fields = [
            "id", "author", "title", "content", "created_at", "is_author","num_answers"
        ]
        read_only_fields = ["id", "author", "created_at", "num_answers"]

    def validate_title(self, value):
        value = strip_tags(value).strip()
        if not value:
            raise serializers.ValidationError("Title cannot be empty.")
        return value

    def validate_content(self, value):
        value = strip_tags(value).strip()
        if not value:
            raise serializers.ValidationError("Content cannot be empty.")
        return value

    def get_is_author(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.author == request.user
        return False

class AnswerSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    question = QuestionSerializer(read_only=True)
    upvote_count = serializers.SerializerMethodField()
    is_upvoted = serializers.SerializerMethodField()
    upvoted_by_names = serializers.SerializerMethodField()
    class Meta:
        model = Answer
        fields = [
            "id", "author", "content", "created_at", "upvote_count", "is_upvoted", "upvoted_by_names", "question", "is_author",
        ]
        read_only_fields = ["id", "question", "author", "created_at"]

    def validate_content(self, value):
        value = strip_tags(value).strip()
        if not value:
            raise serializers.ValidationError("Content cannot be empty.")
        return value

    def get_upvote_count(self, obj):
        return obj.upvotes.count()

    def get_is_upvoted(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return request.user in obj.upvotes.all()

    def get_upvoted_by_names(self, obj):
        return ", ".join(user.username for user in obj.upvotes.all())

    def get_is_author(self, obj):
            request = self.context.get("request")
            if request and request.user.is_authenticated:
                return obj.author == request.user
            return False