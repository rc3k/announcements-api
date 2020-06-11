import html

from django.utils.text import Truncator
from django.utils.timezone import now

from rest_framework import serializers

from .models import Announcement
from .domain import announcement_chars_truncate


class AnnouncementSerializer(serializers.ModelSerializer):

    programme_name = serializers.SlugRelatedField(
        source='programme',
        read_only=True,
        slug_field='display_name'
    )

    recipient = serializers.SerializerMethodField()

    display_id = serializers.SerializerMethodField()

    @staticmethod
    def get_recipient(obj):
        return getattr(obj, 'recipient', '')

    @staticmethod
    def get_display_id(obj):
        return getattr(obj, 'display_id', obj.id)

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user if self.context['request'].user.is_authenticated else None
        return Announcement.objects.create(**validated_data)

    def validate(self, data):
        if data['visible_from'] >= data['visible_to']:
            raise serializers.ValidationError("'visible from' must be before 'visible to'")
        if data['visible_to'] < now():
            raise serializers.ValidationError("'visible to' cannot be in the past")
        return data

    class Meta:
        model = Announcement
        fields = (
            'id',
            'subject',
            'body',
            'visible_from',
            'visible_to',
            'is_urgent',
            'audience',
            'programme',
            'programme_name',
            'recipient',
            'display_id',
            'modified',
            'created'
        )


class UserAnnouncementSerializer(serializers.Serializer):

    @staticmethod
    def get_body(obj):
        body = html.unescape(obj['body'])
        return {
            'body': body,
            'truncated': Truncator(body).chars(announcement_chars_truncate, html=True)
        }

    id = serializers.IntegerField(read_only=True)
    subject = serializers.CharField(read_only=True)
    visible_from = serializers.DateTimeField(read_only=True)
    is_urgent = serializers.BooleanField(read_only=True)
    marked_read = serializers.DateTimeField(allow_null=True)
    modified = serializers.DateTimeField(allow_null=True, read_only=True)
    body = serializers.SerializerMethodField()
