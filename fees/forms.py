"""Forms for the Cashier module."""

from django import forms
from django.db.models import Sum

from accounts.forms import BootstrapFormMixin
from accounts.models import Student

from .models import FeeStructure, Payment


class FeeStructureForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = ["department", "semester", "fee_type", "amount", "description"]


def head_account(student, fee_type):
    """(payable, paid, due) for ONE fee head of a student — all semesters up
    to their current one.  Only CONFIRMED payments count as paid."""
    payable = (
        FeeStructure.objects.filter(
            department=student.department,
            semester__lte=student.semester,
            fee_type=fee_type,
        ).aggregate(t=Sum("amount"))["t"]
        or 0
    )
    paid = (
        Payment.objects.filter(
            student=student, fee_type=fee_type, status="CONFIRMED"
        ).aggregate(t=Sum("amount"))["t"]
        or 0
    )
    return payable, paid, payable - paid


class PaymentForm(BootstrapFormMixin, forms.ModelForm):
    """Record a new payment, enforcing the university's full-payment policy:

    * every fee head is paid IN FULL at once — amount must equal the exact
      remaining due of that head (no installments, no overpayment);
    * the Exam Fee is unlocked only after ALL admission fees are cleared —
      defaulters pay admission + exam together (admission first).
    """

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
        # amount comes from the fee structure, not from the cashier's keyboard
        self.fields["amount"].widget.attrs["readonly"] = True
        self.fields["amount"].help_text = (
            "Auto-filled with the full remaining due of the selected fee head."
        )
        if not self.is_bound:
            from django.utils import timezone

            self.initial.setdefault("payment_date", timezone.localdate())

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get("student")
        fee_type = cleaned.get("fee_type")
        amount = cleaned.get("amount")
        if not (student and fee_type and amount is not None):
            return cleaned

        payable, paid, due = head_account(student, fee_type)
        label = dict(Payment._meta.get_field("fee_type").choices)[fee_type]
        if due <= 0:
            raise forms.ValidationError(
                f"The {label} of {student.user.get_full_name()} is already "
                f"fully paid — nothing to collect."
            )
        if amount != due:
            raise forms.ValidationError(
                f"No installments allowed — the {label} must be paid in full "
                f"at once: exactly ৳{due} (payable ৳{payable} − paid ৳{paid})."
            )
        if fee_type == "EXAM":
            _, _, adm_due = head_account(student, "ADMISSION")
            if adm_due > 0:
                raise forms.ValidationError(
                    f"Exam fee is locked — {student.user.get_full_name()} has an "
                    f"unpaid admission fee of ৳{adm_due}. Students who missed the "
                    f"admission fee must pay BOTH together (admission first, "
                    f"then exam)."
                )
        return cleaned


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
        # the recorded amount is immutable — corrections happen via status
        # (cancel + record again), never by editing the money figure
        self.fields["amount"].disabled = True
        self.fields["fee_type"].disabled = True
        self.fields["status"].help_text = (
            "Confirmed = counts as paid · Pending = awaiting verification · "
            "Cancelled = voided (ignored in accounts)"
        )
