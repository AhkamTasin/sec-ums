from django.contrib import admin

from .models import FeeStructure, Payment


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ("department", "semester", "fee_type", "amount")
    list_filter = ("department", "semester", "fee_type")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_no", "student", "fee_type", "amount", "method", "payment_date")
    search_fields = ("receipt_no", "student__reg_no")
    readonly_fields = ("receipt_no",)
