from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Object, SessionApproval, User, WorkSession


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Role", {"fields": ("role",)}),
    )


@admin.register(Object)
class ObjectAdmin(admin.ModelAdmin):
    list_display = ("address", "latitude", "longitude", "allowed_radius")
    search_fields = ("address",)


@admin.register(WorkSession)
class WorkSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "worker", "object", "check_in", "check_out", "status", "payment")
    list_filter = ("status", "object", "worker")
    search_fields = ("worker__username", "object__address")


@admin.register(SessionApproval)
class SessionApprovalAdmin(admin.ModelAdmin):
    list_display = ("session", "manager", "approved", "reviewed_at")
    list_filter = ("approved", "manager")
    search_fields = ("session__worker__username", "manager__username")
