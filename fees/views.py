"""Views for the Cashier module: fees, payments, bills and receipts."""

from datetime import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import role_required
from accounts.models import Student

from .forms import FeeStructureForm, PaymentForm, PaymentUpdateForm
from .models import (
    FEE_TYPE_CHOICES,
    PAYMENT_METHOD_CHOICES,
    FeeStructure,
    Payment,
)
from .services import amount_in_words, compute_all_dues, student_account

CONFIRMED = {"status": "CONFIRMED"}


def monthly_collection_chart():
    today = timezone.localdate().replace(day=1)
    months = []
    for i in range(5, -1, -1):
        y, m = today.year, today.month - i
        while m <= 0:
            m += 12
            y -= 1
        months.append((y, m))
    qs = (
        Payment.objects.filter(**CONFIRMED)
        .annotate(month=TruncMonth("payment_date"))
        .values("month")
        .annotate(total=Sum("amount"))
    )
    mapping = {c["month"].strftime("%Y-%m"): float(c["total"]) for c in qs}
    return {
        "labels": [f"{y}-{m:02d}" for y, m in months],
        "data": [mapping.get(f"{y}-{m:02d}", 0) for y, m in months],
    }


# ---------------------------------------------------------------------------
# Cashier dashboard
# ---------------------------------------------------------------------------
@role_required("CASHIER")
def cashier_dashboard(request):
    from academics.views import visible_notices

    today = timezone.localdate()
    month_start = today.replace(day=1)

    due_rows = compute_all_dues()
    owing = [r for r in due_rows if r["due"] > 0]
    cleared = [r for r in due_rows if r["due"] <= 0]

    today_qs = Payment.objects.filter(payment_date=today, **CONFIRMED)
    pending_qs = Payment.objects.filter(status="PENDING")

    context = {
        "today_collection": today_qs.aggregate(t=Sum("amount"))["t"] or 0,
        "today_count": today_qs.count(),
        "month_collection": Payment.objects.filter(
            payment_date__gte=month_start, **CONFIRMED
        ).aggregate(t=Sum("amount"))["t"]
        or 0,
        "total_collection": Payment.objects.filter(**CONFIRMED).aggregate(
            t=Sum("amount")
        )["t"]
        or 0,
        "total_due": sum(r["due"] for r in owing),
        "students_with_due": len(owing),
        "paid_students": len(cleared),
        "pending_amount": pending_qs.aggregate(t=Sum("amount"))["t"] or 0,
        "pending_count": pending_qs.count(),
        "recent_payments": Payment.objects.select_related("student__user")[:8],
        "monthly_collections": monthly_collection_chart(),
        "notices": visible_notices(request.user, limit=5),
    }
    return render(request, "cashier/dashboard.html", context)


# ---------------------------------------------------------------------------
# Fee structure management
# ---------------------------------------------------------------------------
@role_required("CASHIER")
def fee_structure_list(request):
    from academics.models import Department

    structures = FeeStructure.objects.select_related("department")
    dept = request.GET.get("dept")
    sem = request.GET.get("sem")
    if dept:
        structures = structures.filter(department__code=dept)
    if sem:
        structures = structures.filter(semester=sem)
    return render(
        request,
        "cashier/fee_structures.html",
        {
            "structures": structures,
            "departments": Department.objects.all(),
            "semesters": range(1, 9),
            "dept": dept or "",
            "sem": sem or "",
        },
    )


@role_required("CASHIER")
def fee_structure_add(request):
    form = FeeStructureForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Fee structure saved.")
        return redirect("fees:fee_structures")
    return render(
        request,
        "cashier/fee_form.html",
        {"form": form, "title": "Add Fee Structure"},
    )


@role_required("CASHIER")
def fee_structure_edit(request, pk):
    structure = get_object_or_404(FeeStructure, pk=pk)
    form = FeeStructureForm(request.POST or None, instance=structure)
    if form.is_valid():
        form.save()
        messages.success(request, "Fee structure updated.")
        return redirect("fees:fee_structures")
    return render(
        request,
        "cashier/fee_form.html",
        {"form": form, "title": f"Edit Fee Structure — {structure}"},
    )


# ---------------------------------------------------------------------------
# Payments & receipts
# ---------------------------------------------------------------------------
@role_required("CASHIER")
def payment_list(request):
    """Payment history with search (receipt / reg no / name) and filters."""
    payments = Payment.objects.select_related("student__user", "student__department")
    q = request.GET.get("q", "").strip()
    date_from = request.GET.get("from", "")
    date_to = request.GET.get("to", "")
    method = request.GET.get("method", "")
    status = request.GET.get("status", "")
    if q:
        payments = payments.filter(
            Q(receipt_no__icontains=q)
            | Q(student__reg_no__icontains=q)
            | Q(student__user__first_name__icontains=q)
            | Q(student__user__last_name__icontains=q)
        )
    for value, lookup in ((date_from, "payment_date__gte"), (date_to, "payment_date__lte")):
        if value:
            try:
                payments = payments.filter(**{lookup: datetime.strptime(value, "%Y-%m-%d")})
            except ValueError:
                pass
    if method:
        payments = payments.filter(method=method)
    if status:
        payments = payments.filter(status=status)
    summary = payments.aggregate(t=Sum("amount"))["t"] or 0
    confirmed_total = payments.filter(**CONFIRMED).aggregate(t=Sum("amount"))["t"] or 0
    page_obj = Paginator(payments, 15).get_page(request.GET.get("page"))
    qs = request.GET.copy()
    qs.pop("page", None)
    return render(
        request,
        "cashier/payments.html",
        {
            "payments": page_obj,
            "page_obj": page_obj,
            "qs_suffix": qs.urlencode(),
            "summary": summary,
            "confirmed_total": confirmed_total,
            "q": q,
            "date_from": date_from,
            "date_to": date_to,
            "method": method,
            "status": status,
            "methods": PAYMENT_METHOD_CHOICES,
            "statuses": [
                ("CONFIRMED", "Confirmed"),
                ("PENDING", "Pending Verification"),
                ("CANCELLED", "Cancelled"),
            ],
        },
    )


@role_required("CASHIER")
def payment_record(request):
    initial = {}
    student_id = request.GET.get("student")
    if student_id:
        initial["student"] = student_id
    form = PaymentForm(request.POST or None, initial=initial)
    if form.is_valid():
        payment = form.save(commit=False)
        payment.received_by = request.user
        payment.save()
        messages.success(request, f"Payment recorded. Receipt {payment.receipt_no}.")
        return redirect("fees:receipt", pk=payment.pk)
    return render(request, "cashier/payment_form.html", {"form": form})


@role_required("CASHIER")
def payment_edit(request, pk):
    """Update payment details / status (confirm pending money, fix mistakes,
    or cancel a wrong entry). Receipt number and student stay the same."""
    payment = get_object_or_404(
        Payment.objects.select_related("student__user", "student__department"), pk=pk
    )
    old_status = payment.status
    form = PaymentUpdateForm(request.POST or None, instance=payment)
    if request.method == "POST" and form.is_valid():
        updated = form.save()
        if old_status != updated.status:
            messages.success(
                request,
                f"Receipt {updated.receipt_no}: status changed "
                f"{old_status.title()} → {updated.get_status_display()}.",
            )
        else:
            messages.success(request, f"Receipt {updated.receipt_no} updated.")
        return redirect("fees:receipt", pk=updated.pk)
    return render(request, "cashier/payment_edit.html", {"form": form, "payment": payment})


@role_required("CASHIER")
def payment_receipt(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related(
            "student__user", "student__department", "received_by"
        ),
        pk=pk,
    )
    payable, paid, due = student_account(payment.student)
    return render(
        request,
        "cashier/receipt.html",
        {
            "payment": payment,
            "payable": payable,
            "paid": paid,
            "remaining_due": due,
            "words": amount_in_words(payment.amount),
        },
    )


# ---------------------------------------------------------------------------
# Daily collection report
# ---------------------------------------------------------------------------
@role_required("CASHIER")
def daily_report(request):
    """Printable daily collection report: all receipts of one day, totals by
    method and fee type, and the cashier who received each payment."""
    date_str = request.GET.get("date", "")
    try:
        report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        report_date = timezone.localdate()
        date_str = report_date.isoformat()

    payments = (
        Payment.objects.filter(payment_date=report_date)
        .select_related("student__user", "student__department", "received_by")
        .order_by("id")
    )
    confirmed = payments.filter(**CONFIRMED)
    total = confirmed.aggregate(t=Sum("amount"))["t"] or 0

    by_method = (
        confirmed.values("method")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    for row in by_method:
        row["label"] = dict(PAYMENT_METHOD_CHOICES).get(row["method"], row["method"])

    by_fee_type = (
        confirmed.values("fee_type")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    for row in by_fee_type:
        row["label"] = dict(FEE_TYPE_CHOICES).get(row["fee_type"], row["fee_type"])

    by_cashier = (
        confirmed.values("received_by__first_name", "received_by__last_name", "received_by__username")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    context = {
        "report_date": report_date,
        "date_str": date_str,
        "payments": payments,
        "receipt_count": confirmed.count(),
        "total": total,
        "pending_count": payments.filter(status="PENDING").count(),
        "cancelled_count": payments.filter(status="CANCELLED").count(),
        "by_method": by_method,
        "by_fee_type": by_fee_type,
        "by_cashier": by_cashier,
        "words": amount_in_words(total),
    }
    template = "cashier/daily_report_print.html" if request.GET.get("print") == "1" else "cashier/daily_report.html"
    return render(request, template, context)


# ---------------------------------------------------------------------------
# Dues & bills
# ---------------------------------------------------------------------------
@role_required("CASHIER")
def dues_list(request):
    rows = compute_all_dues()
    show_all = request.GET.get("all") == "1"
    if not show_all:
        rows = [r for r in rows if r["due"] > 0]
    return render(
        request, "cashier/dues.html", {"rows": rows, "show_all": show_all}
    )


@role_required("CASHIER")
def student_statement(request, student_id):
    """Printable bill: fees charged vs payments made for one student."""
    from fees.models import FeeStructure

    student = get_object_or_404(
        Student.objects.select_related("user", "department"), pk=student_id
    )
    structures = FeeStructure.objects.filter(
        department=student.department, semester__lte=student.semester
    )
    payments = Payment.objects.filter(student=student, status="CONFIRMED")
    pending = Payment.objects.filter(student=student, status="PENDING")
    payable, paid, due = student_account(student)
    return render(
        request,
        "cashier/statement.html",
        {
            "student": student,
            "structures": structures,
            "payments": payments,
            "pending": pending,
            "payable": payable,
            "paid": paid,
            "due": due,
        },
    )
