from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import Team, User


class AdminTeamCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = (
            "id",
            "name",
            "description",
        )
        read_only_fields = ("id",)


class AdminUserResponseSerializer(serializers.ModelSerializer):
    team_id = serializers.IntegerField(read_only=True)
    team_name = serializers.CharField(
        source="team.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "team_id",
            "team_name",
            "is_active",
        )
        read_only_fields = fields


class AdminUserManagementSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(
        required=False,
        min_value=1,
    )

    username = serializers.CharField(
        required=False,
        max_length=150,
        validators=User._meta.get_field("username").validators,
    )

    email = serializers.EmailField(
        required=False,
        max_length=254,
    )

    password = serializers.CharField(
        required=False,
        write_only=True,
        trim_whitespace=False,
        allow_blank=False,
    )

    first_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )

    last_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )

    role = serializers.ChoiceField(
        choices=User.Role.choices,
        required=False,
    )

    team_id = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(),
        source="team",
        required=False,
        allow_null=True,
    )

    is_active = serializers.BooleanField(
        required=False,
    )

    def validate(self, attrs):
        target_user = self.instance

        if target_user is None:
            required_fields = (
                "username",
                "email",
                "password",
            )

            errors = {
                field: ["This field is required."]
                for field in required_fields
                if field not in attrs
            }

            if errors:
                raise serializers.ValidationError(errors)

        elif set(attrs) == {"user_id"}:
            raise serializers.ValidationError(
                "At least one field must be provided for update."
            )

        username = attrs.get(
            "username",
            getattr(target_user, "username", ""),
        )

        email = attrs.get(
            "email",
            getattr(target_user, "email", ""),
        )

        if "email" in attrs:
            attrs["email"] = User.objects.normalize_email(email)
            email = attrs["email"]

        users = User.objects.all()

        if target_user is not None:
            users = users.exclude(pk=target_user.pk)

        if users.filter(username=username).exists():
            raise serializers.ValidationError(
                {"username": "A user with this username already exists."}
            )

        if users.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                {"email": "A user with this email already exists."}
            )

        role = attrs.get(
            "role",
            getattr(
                target_user,
                "role",
                User.Role.TEAM_MEMBER,
            ),
        )

        team = attrs.get(
            "team",
            getattr(target_user, "team", None),
        )

        if role == User.Role.TEAM_MEMBER and team is None:
            raise serializers.ValidationError(
                {"team_id": "TEAM_MEMBER users must belong to a team."}
            )

        request = self.context.get("request")

        if (
            request is not None
            and target_user is not None
            and target_user.pk == request.user.pk
        ):
            if attrs.get("is_active") is False:
                raise serializers.ValidationError(
                    {"is_active": "You cannot deactivate your own account."}
                )

            if role != User.Role.ADMIN:
                raise serializers.ValidationError(
                    {"role": "You cannot remove your own ADMIN role."}
                )

        if "password" in attrs:
            password_user = User(
                username=username,
                email=email,
                first_name=attrs.get(
                    "first_name",
                    getattr(target_user, "first_name", ""),
                ),
                last_name=attrs.get(
                    "last_name",
                    getattr(target_user, "last_name", ""),
                ),
            )

            try:
                validate_password(
                    attrs["password"],
                    user=password_user,
                )
            except DjangoValidationError as exc:
                raise serializers.ValidationError(
                    {"password": exc.messages}
                ) from exc

        return attrs

    def create(self, validated_data):
        validated_data.pop("user_id", None)

        password = validated_data.pop("password")

        validated_data.setdefault(
            "role",
            User.Role.TEAM_MEMBER,
        )

        validated_data.setdefault("is_active", True)

        return User.objects.create_user(
            password=password,
            **validated_data,
        )

    def update(self, instance, validated_data):
        validated_data.pop("user_id", None)

        password = validated_data.pop("password", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        if password is not None:
            instance.set_password(password)

        instance.save()

        return instance

class AdminUserIdSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    