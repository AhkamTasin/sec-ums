"""Shared money calculations for the Fees / Cashier module."""

from django.db.models import Sum

from accounts.models import Student

from .models import FeeStructure, Payment


def student_account(student):
    """Return (total_payable, total_paid, due) for a student.

    A student is liable for every fee structure of their department up to and
    including their current semester; dues = payable - paid.  Only CONFIRMED
    payments count as paid (pending/cancelled are ignored).
    """
    payable = (
        FeeStructure.objects.filter(
            department=student.department, semester__lte=student.semester
        ).aggregate(t=Sum("amount"))["t"]
        or 0
    )
    paid = (
        Payment.objects.filter(student=student, status="CONFIRMED").aggregate(
            t=Sum("amount")
        )["t"]
        or 0
    )
    return payable, paid, payable - paid


def compute_all_dues():
    """Row per student: {student, payable, paid, due}"""
    rows = []
    for student in Student.objects.select_related("user", "department"):
        payable, paid, due = student_account(student)
        rows.append(
            {"student": student, "payable": payable, "paid": paid, "due": due}
        )
    rows.sort(key=lambda r: r["due"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Amount in words (for printable receipts)
# ---------------------------------------------------------------------------
_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
    "Eighty", "Ninety",
]


def _three_digits(n):
    """Words for 0..999."""
    words = ""
    if n >= 100:
        words += _ONES[n // 100] + " Hundred"
        n %= 100
        if n:
            words += " "
    if n >= 20:
        words += _TENS[n // 10]
        if n % 10:
            words += "-" + _ONES[n % 10]
    elif n > 0:
        words += _ONES[n]
    return words


def amount_in_words(amount):
    """'Taka Twelve Thousand Five Hundred Only' for a decimal amount."""
    n = int(round(amount))
    if n == 0:
        return "Taka Zero Only"
    parts = []
    for value, label in ((10_000_000, "Crore"), (100_000, "Lakh"), (1_000, "Thousand")):
        if n >= value:
            group, n = divmod(n, value)
            parts.append(_three_digits(group) + " " + label)
    if n:
        parts.append(_three_digits(n))
    return "Taka " + " ".join(parts) + " Only"
