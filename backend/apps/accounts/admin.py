from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("ABF-FST role", {"fields": ("role", "phone")}),
    )
    list_display = ("username", "email", "role", "is_staff")
    list_filter = DjangoUserAdmin.list_filter + ("role",)
