from rest_framework import serializers

from accounts.models import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class UserProfileSerializer(serializers.ModelSerializer):
    team_id = serializers.IntegerField(source="team.id", allow_null=True, read_only=True)
    team_name = serializers.CharField(source="team.name", allow_null=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "team_id",
            "team_name",
        ]