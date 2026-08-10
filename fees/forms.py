"""Forms for the Cashier module."""

from django import forms

from accounts.forms import BootstrapFormMixin
from accounts.models import Student

from .models import FeeStructure, Payment


class FeeStructureForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = ["department", "semester", "fee_type", "amount", "description"]


class PaymentForm(BootstrapFormMixin, forms.ModelForm):
    """Record a new payment. Brand-new payments are Confirmed by default, or
    kept Pending when the money still needs verification (e.g. bank slip)."""

    class Meta:
        model = Payment
        fields = [
            "student", "fee_type", "amount", "method", "status",
            "payment_date", "note",
        ]
        widgets = {"payment_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.select_related(
            "user", "department"
        )
        self.fields["student"].label_from_instance = (
            lambda s: f"{s.reg_no} — {s.user.get_full_name()} ({s.department.code}, Sem {s.semester})"
        )
        # a cancelled payment cannot be created — that state only makes sense
        # when correcting an existing record
        self.fields["status"].choices = [
            ("CONFIRMED", "Confirmed — money received"),
            ("PENDING", "Pending — verify later"),
        ]
        self.fields["status"].help_text = (
            "Pending payments do NOT reduce the student's due until confirmed."
        )
        self.fields["note"].required = False
        if not self.is_bound:
            from django.utils import timezone

            self.initial.setdefault("payment_date", timezone.localdate())


class PaymentUpdateForm(BootstrapFormMixin, forms.ModelForm):
    """Update an existing payment (correct mistakes, confirm pending money,
    or cancel a wrong entry). The student and receipt number never change."""

    class Meta:
        model = Payment
        fields = ["fee_type", "amount", "method", "status", "payment_date", "note"]
        widgets = {"payment_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["note"].required = False
        self.fields["status"].help_text = (
            "Confirmed = counts as paid · Pending = awaiting verification · "
            "Cancelled = voided (ignored in accounts)"
        )
