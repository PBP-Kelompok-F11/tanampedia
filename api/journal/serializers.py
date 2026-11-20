from django.core.validators import URLValidator
from rest_framework import serializers

from journal.models import JournalEntry, PlantJournal


http_url = URLValidator(schemes=['http', 'https'])


class JournalListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True)
    q = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=['all', *PlantJournal.Status.values], default='all')
    liked = serializers.ChoiceField(choices=['all', '1'], default='all')
    sort = serializers.ChoiceField(choices=['latest', 'newest', 'most_liked'], default='latest')


class JournalListSerializer(serializers.ModelSerializer):
    likes_count = serializers.IntegerField(read_only=True)
    is_liked = serializers.BooleanField(read_only=True)

    class Meta:
        model = PlantJournal
        fields = ('id', 'user', 'plant_name', 'thumbnail', 'status', 'start_date',
                  'is_public', 'likes_count', 'is_liked')
        read_only_fields = fields


class PlantJournalSerializer(JournalListSerializer):
    thumbnail = serializers.CharField(
        required=False, allow_blank=True, validators=[http_url],
        max_length=PlantJournal._meta.get_field('thumbnail').max_length,
    )
    entry_count = serializers.IntegerField(source='entries.count', read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta(JournalListSerializer.Meta):
        fields = JournalListSerializer.Meta.fields + (
            'description', 'growing_medium', 'location', 'entry_count', 'is_owner',
        )
        read_only_fields = ('id', 'user', 'start_date')

    def get_is_owner(self, journal):
        return journal.user_id == self.context['request'].user.pk


class JournalEntrySerializer(serializers.ModelSerializer):
    image = serializers.CharField(
        required=False, allow_blank=True, validators=[http_url],
        max_length=JournalEntry._meta.get_field('image').max_length,
    )

    class Meta:
        model = JournalEntry
        fields = ('id', 'journal', 'header', 'content', 'image',
                  'plant_condition', 'created_at')
        read_only_fields = ('id', 'journal', 'created_at')
