from django.contrib import admin

from .models import CostEvent


@admin.register(CostEvent)
class CostEventAdmin(admin.ModelAdmin):
    list_display = ("date", "category", "amount", "currency", "sample_case", "kii_record", "approved_by")
    list_filter = ("category", "currency")
