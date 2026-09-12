from django.contrib import admin

from .models import IdentifierSequence, Organisation, SampleCase, StratumDefinition


@admin.register(StratumDefinition)
class StratumDefinitionAdmin(admin.ModelAdmin):
    list_display = ("code", "province", "actor_family", "size_class", "target_count")
    list_filter = ("province", "actor_family", "size_class")


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("master_id", "name", "province", "verification_status")
    list_filter = ("province", "verification_status", "actor_family")
    search_fields = ("master_id", "name")
    readonly_fields = ("master_id",)


@admin.register(SampleCase)
class SampleCaseAdmin(admin.ModelAdmin):
    list_display = ("sample_id", "organisation", "sample_type", "status", "workflow_status")
    list_filter = ("sample_type", "status", "workflow_status")
    search_fields = ("sample_id", "organisation__name", "organisation__master_id")
    readonly_fields = ("sample_id",)


@admin.register(IdentifierSequence)
class IdentifierSequenceAdmin(admin.ModelAdmin):
    list_display = ("key", "last_value")
    readonly_fields = ("key", "last_value")

    def has_add_permission(self, request):
        return False
