from django.urls import path

from bookings.views import (
    AdminApproveBookingView,
    AdminBookingListView,
    AdminRejectBookingView,
)

urlpatterns = [
    path("bookings/", AdminBookingListView.as_view(), name="admin-booking-list"),
    path("bookings", AdminBookingListView.as_view(), name="admin-booking-list-no-slash"),
    path(
        "bookings/<int:booking_id>/approve/",
        AdminApproveBookingView.as_view(),
        name="admin-booking-approve",
    ),
    path(
        "bookings/<int:booking_id>/approve",
        AdminApproveBookingView.as_view(),
        name="admin-booking-approve-no-slash",
    ),
    path(
        "bookings/<int:booking_id>/reject/",
        AdminRejectBookingView.as_view(),
        name="admin-booking-reject",
    ),
    path(
        "bookings/<int:booking_id>/reject",
        AdminRejectBookingView.as_view(),
        name="admin-booking-reject-no-slash",
    ),
]

