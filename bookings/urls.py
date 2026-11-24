from django.urls import path

from bookings.views import (
    BookingListCreateView,
    CancelOwnPendingBookingView,
    MyTeamRequestsView,
    ScheduleListView,
)

urlpatterns = [
    path("", BookingListCreateView.as_view(), name="booking-list-create"),
    path("schedule/", ScheduleListView.as_view(), name="booking-schedule"),
    path("schedule", ScheduleListView.as_view(), name="booking-schedule-no-slash"),
    path("my-requests/", MyTeamRequestsView.as_view(), name="booking-my-requests"),
    path("my-requests", MyTeamRequestsView.as_view(), name="booking-my-requests-no-slash"),
    path(
        "<int:booking_id>/cancel/",
        CancelOwnPendingBookingView.as_view(),
        name="booking-cancel",
    ),
    path(
        "<int:booking_id>/cancel",
        CancelOwnPendingBookingView.as_view(),
        name="booking-cancel-no-slash",
    ),
]