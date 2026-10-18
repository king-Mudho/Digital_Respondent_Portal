from django.contrib import admin

from .models import CostEvent


@admin.register(CostEvent)
class CostEventAdmin(admin.ModelAdmin):
    list_display = ("date", "category", "description", "paid_to", "amount", "currency", "approved_by")
    search_fields = ("description", "paid_to")
    list_filter = ("category", "currency")
