from django.contrib.auth import get_user_model
from rest_framework import serializers

from notifications.models import Notification
from organizations.models import Organization

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name")
        read_only_fields = ("id", "username", "email")


class OrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ("id", "name", "slug", "role")

    def get_role(self, obj):
        request = self.context.get("request")
        return obj.get_role(request.user) if request else None


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "verb", "url", "unread", "created_at")
        read_only_fields = fields
