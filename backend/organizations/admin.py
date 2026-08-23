from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from organizations.models import Invitation, Membership, Organization


class MembershipInline(TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(ModelAdmin):
    list_display = ("organization", "user", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("organization__name", "user__username", "user__email")


@admin.register(Invitation)
class InvitationAdmin(ModelAdmin):
    list_display = ("email", "organization", "role", "created_at", "accepted_at")
    list_filter = ("role",)
    search_fields = ("email", "organization__name")
    readonly_fields = ("token",)
