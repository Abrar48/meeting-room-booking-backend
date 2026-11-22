from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import Team, User


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("id", "username", "email", "role", "team", "is_staff")
    list_filter = ("role", "team", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Role & Team Info", {"fields": ("role", "team")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Role & Team Info", {"fields": ("email", "role", "team")}),
    )