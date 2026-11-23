from rest_framework import serializers

from bookings.models import Booking


class PublicScheduleBookingSerializer(serializers.ModelSerializer):
    team_id = serializers.IntegerField(source="team.id", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "team_id",
            "team_name",
            "purpose",
            "start_time",
            "end_time",
            "status",
        ]


class AdminScheduleBookingSerializer(PublicScheduleBookingSerializer):
    requester_id = serializers.IntegerField(source="requester.id", read_only=True)
    requester_username = serializers.CharField(source="requester.username", read_only=True)

    class Meta(PublicScheduleBookingSerializer.Meta):
        fields = PublicScheduleBookingSerializer.Meta.fields + [
            "requester_id",
            "requester_username",
            "notes",
            "decision_note",
        ]


class BookingCreateSerializer(serializers.Serializer):
    team_id = serializers.IntegerField(required=False, allow_null=True)
    purpose = serializers.CharField(max_length=255, required=True)
    start_time = serializers.DateTimeField(required=True)
    end_time = serializers.DateTimeField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class BookingDetailSerializer(serializers.ModelSerializer):
    team_id = serializers.IntegerField(source="team.id", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    requester_id = serializers.IntegerField(source="requester.id", read_only=True)
    requester_username = serializers.CharField(source="requester.username", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "team_id",
            "team_name",
            "requester_id",
            "requester_username",
            "purpose",
            "start_time",
            "end_time",
            "status",
            "notes",
            "decision_note",
            "created_at",
            "updated_at",
        ]


class AdminBookingListSerializer(serializers.ModelSerializer):
    team_id = serializers.IntegerField(source="team.id", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    requester = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "team_id",
            "team_name",
            "requester",
            "purpose",
            "start_time",
            "end_time",
            "status",
            "notes",
            "decision_note",
            "created_at",
            "updated_at",
        ]

    def get_requester(self, obj):
        return {
            "id": obj.requester.id,
            "username": obj.requester.username,
            "email": obj.requester.email,
            "first_name": obj.requester.first_name,
            "last_name": obj.requester.last_name,
        }


class AdminDecisionSerializer(serializers.Serializer):
    decision_note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )


class AdminCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
    )


class AdminReassignSerializer(serializers.Serializer):
    target_booking_id = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
    )
    decision_note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )