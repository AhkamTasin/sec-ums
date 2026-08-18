"""Fee structures and student payments (Cashier module)."""

from django.db import models
from django.utils import timezone

FEE_TYPE_CHOICES = [
    ("ADMISSION", "Admission Fee"),
    ("EXAM", "Exam Fee"),
]

PAYMENT_METHOD_CHOICES = [
    ("CASH", "Cash"),
    ("BANK", "Bank Deposit"),
    ("CARD", "Card"),
    ("MOBILE", "Mobile Banking"),
]

PAYMENT_STATUS_CHOICES = [
    ("CONFIRMED", "Confirmed"),
    ("PENDING", "Pending Verification"),
    ("CANCELLED", "Cancelled"),
]


class FeeStructure(models.Model):
    """The amount a department's students must pay for a fee type in a semester."""

    department = models.ForeignKey(
        "academics.Department", on_delete=models.CASCADE, related_name="fee_structures"
    )
    semester = models.PositiveSmallIntegerField(choices=[(i, f"Semester {i}") for i in range(1, 9)])
    fee_type = models.CharField(max_length=15, choices=FEE_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ("department", "semester", "fee_type")
        ordering = ["department", "semester", "fee_type"]

    def __str__(self):
        return (
            f"{self.department.code} Sem-{self.semester} "
            f"{self.get_fee_type_display()}: ৳{self.amount}"
        )


class Payment(models.Model):
    """A recorded fee payment by a student, with a printable receipt."""

    receipt_no = models.CharField(max_length=20, unique=True, editable=False)
    student = models.ForeignKey(
        "accounts.Student", on_delete=models.CASCADE, related_name="payments"
    )
    # University policy: every fee head is paid IN FULL, in a single payment —
    # no installments.  The Exam Fee is unlocked only after ALL admission fees
    # are cleared (defaulters pay both together).  Enforced by PaymentForm.
    fee_type = models.CharField(max_length=15, choices=FEE_TYPE_CHOICES, default="ADMISSION")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default="CASH")
    status = models.CharField(
        max_length=10, choices=PAYMENT_STATUS_CHOICES, default="CONFIRMED",
        help_text="Only Confirmed payments count towards a student's paid fees.",
    )
    payment_date = models.DateField(default=timezone.localdate)
    note = models.CharField(max_length=200, blank=True)
    received_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]

    def save(self, *args, **kwargs):
        if not self.receipt_no:
            super().save(*args, **kwargs)  # ensure pk exists
            self.receipt_no = f"RC-{self.payment_date:%Y%m%d}-{self.pk:05d}"
            if "update_fields" not in kwargs:
                kwargs["force_insert"] = False
            super().save(update_fields=["receipt_no"])
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_no} — {self.student.reg_no} — ৳{self.amount}"
