from django.urls import path

from accounts.views import AdminCheckView, LoginView, MeView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("admin-only/", AdminCheckView.as_view(), name="auth-admin-only"),
]