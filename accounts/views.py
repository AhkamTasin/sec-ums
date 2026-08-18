"""Views: authentication, Super Admin module and dashboard dispatch."""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from accounts.decorators import role_required
from accounts.forms import (
    DepartmentAdminCreateForm,
    DepartmentAdminUpdateForm,
    DepartmentForm,
    NoticeForm,
    StaffUserCreateForm,
    StudentCreateForm,
    StyledAuthenticationForm,
    TeacherCreateForm,
    TeacherUpdateForm,
)
from accounts.models import DepartmentAdmin, Student, Teacher, User


# ---------------------------------------------------------------------------
# Root & dashboard dispatch
# ---------------------------------------------------------------------------
def landing(request):
    """Public landing page — the college website front of the UMS.

    Shows the institution, quick stats, latest global notices and a
    login/dashboard entry point. If a real campus photo is dropped at
    ``static/img/campus.jpg`` it is used as the hero background.
    """
    from academics.models import Course, Department, Notice

    campus_file = settings.BASE_DIR / "static" / "img" / "campus.jpg"
    context = {
        "campus_image": "img/campus.jpg" if campus_file.exists() else None,
        "notices": Notice.objects.filter(department__isnull=True).select_related(
            "created_by"
        )[:6],
        "departments": Department.objects.all(),
        "stats": {
            "students": Student.objects.count(),
            "teachers": Teacher.objects.count(),
            "departments": Department.objects.count(),
            "courses": Course.objects.count(),
        },
    }
    return render(request, "landing.html", context)


@login_required
def dashboard_redirect(request):
    return redirect(request.user.dashboard_url)


# ---------------------------------------------------------------------------
# Authentication (login / logout / password management)
# ---------------------------------------------------------------------------
class UMSLoginView(auth_views.LoginView):
    template_name = "login.html"
    authentication_form = StyledAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse(
            self.request.user.dashboard_url
        )


# ---------------------------------------------------------------------------
# Password management (change while logged in + self-service reset)
# ---------------------------------------------------------------------------
class UMSPasswordChangeView(auth_views.PasswordChangeView):
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("accounts:password_change_done")


class UMSPasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = "registration/password_change_done.html"


class UMSPasswordResetView(auth_views.PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class UMSPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"


class UMSPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class UMSPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "registration/password_reset_complete.html"


# ---------------------------------------------------------------------------
# Admin module — dashboard
# ---------------------------------------------------------------------------
@role_required("SUPER_ADMIN")
def admin_dashboard(request):
    from academics.models import Course, Department, Notice
    from fees.models import Payment
    from fees.services import compute_all_dues
    from library.models import Book, BookIssue

    today = timezone.localdate()

    # Students per department (bar chart)
    dept_qs = (
        Student.objects.values("department__code")
        .annotate(count=Count("id"))
        .order_by("department__code")
    )
    students_per_dept = {
        "labels": [d["department__code"] for d in dept_qs],
        "data": [d["count"] for d in dept_qs],
    }

    # Collections for the last 6 months (line chart)
    month_start = today.replace(day=1)
    months = []
    for i in range(5, -1, -1):
        # naive month arithmetic good enough for labels
        y = month_start.year
        m = month_start.month - i
        while m <= 0:
            m += 12
            y -= 1
        months.append((y, m))
    collections_qs = (
        Payment.objects.filter(status="CONFIRMED")
        .annotate(month=TruncMonth("payment_date"))
        .values("month")
        .annotate(total=Sum("amount"))
    )
    collections_map = {c["month"].strftime("%Y-%m"): c["total"] for c in collections_qs}
    monthly_collections = {
        "labels": [f"{y}-{m:02d}" for y, m in months],
        "data": [float(collections_map.get(f"{y}-{m:02d}", 0) or 0) for y, m in months],
    }

    due_rows = compute_all_dues()
    total_due = sum(row["due"] for row in due_rows if row["due"] > 0)

    context = {
        "total_students": Student.objects.count(),
        "total_teachers": Teacher.objects.count(),
        "total_courses": Course.objects.count(),
        "total_departments": Department.objects.count(),
        "total_books": Book.objects.count(),
        "books_issued": BookIssue.objects.filter(status="ISSUED").count(),
        "total_collected": Payment.objects.filter(status="CONFIRMED").aggregate(t=Sum("amount"))["t"] or 0,
        "total_due": total_due,
        "total_notices": Notice.objects.count(),
        "recent_payments": Payment.objects.select_related("student__user")[:5],
        "recent_notices": Notice.objects.select_related("created_by")[:5],
        "students_per_dept": students_per_dept,
        "monthly_collections": monthly_collections,
    }
    return render(request, "adminpanel/dashboard.html", context)


# ---------------------------------------------------------------------------
# Admin module — student records
# ---------------------------------------------------------------------------
@role_required("SUPER_ADMIN")
def manage_students(request):
    q = request.GET.get("q", "").strip()
    students = Student.objects.select_related("user", "department")
    if q:
        from django.db.models import Q

        students = students.filter(
            Q(reg_no__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
        )
    return render(
        request,
        "adminpanel/students.html",
        {"students": students, "q": q},
    )


@role_required("SUPER_ADMIN")
def add_student(request):
    form = StudentCreateForm(request.POST or None)
    if form.is_valid():
        student = form.save()
        messages.success(
            request,
            f"Student {student.user.get_full_name()} ({student.reg_no}) created. "
            f"Login: {student.reg_no} / {form.cleaned_data['password']}",
        )
        return redirect("accounts:manage_students")
    return render(
        request,
        "adminpanel/student_form.html",
        {
            "form": form,
            "title": "Add New Student",
            "cancel_url": reverse("accounts:manage_students"),
        },
    )


# ---------------------------------------------------------------------------
# Admin module — teacher records
# ---------------------------------------------------------------------------
@role_required("SUPER_ADMIN")
def manage_teachers(request):
    q = request.GET.get("q", "").strip()
    teachers = Teacher.objects.select_related("user", "department")
    if q:
        from django.db.models import Q

        teachers = teachers.filter(
            Q(employee_id__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
        )
    return render(
        request, "adminpanel/teachers.html", {"teachers": teachers, "q": q}
    )


@role_required("SUPER_ADMIN")
def add_teacher(request):
    form = TeacherCreateForm(request.POST or None)
    if form.is_valid():
        teacher = form.save()
        messages.success(
            request,
            f"Teacher {teacher.user.get_full_name()} ({teacher.employee_id}) created. "
            f"Login: {teacher.employee_id} / {form.cleaned_data['password']}",
        )
        return redirect("accounts:manage_teachers")
    return render(
        request,
        "adminpanel/teacher_form.html",
        {
            "form": form,
            "title": "Add New Teacher",
            "cancel_url": reverse("accounts:manage_teachers"),
        },
    )


@role_required("SUPER_ADMIN")
def edit_teacher(request, pk):
    teacher = get_object_or_404(Teacher.objects.select_related("user"), pk=pk)
    form = TeacherUpdateForm(request.POST or None, teacher=teacher)
    if form.is_valid():
        form.save()
        messages.success(request, f"Teacher {teacher.employee_id} updated.")
        return redirect("accounts:manage_teachers")
    return render(
        request,
        "adminpanel/teacher_form.html",
        {
            "form": form,
            "title": f"Update Teacher — {teacher.employee_id}",
            "cancel_url": reverse("accounts:manage_teachers"),
        },
    )


# ---------------------------------------------------------------------------
# Admin module — notice management
# ---------------------------------------------------------------------------
@role_required("SUPER_ADMIN")
def manage_notices(request):
    from academics.models import Notice

    notices = Notice.objects.select_related("created_by")
    return render(request, "adminpanel/notices_manage.html", {"notices": notices})


@role_required("SUPER_ADMIN")
def add_notice(request):
    form = NoticeForm(request.POST or None)
    if form.is_valid():
        notice = form.save(commit=False)
        notice.created_by = request.user
        notice.save()
        messages.success(request, "Notice published.")
        return redirect("accounts:manage_notices")
    return render(
        request, "adminpanel/notice_form.html", {"form": form, "title": "Publish Notice"}
    )


@role_required("SUPER_ADMIN")
def edit_notice(request, pk):
    from academics.models import Notice

    notice = get_object_or_404(Notice, pk=pk)
    form = NoticeForm(request.POST or None, instance=notice)
    if form.is_valid():
        form.save()
        messages.success(request, "Notice updated.")
        return redirect("accounts:manage_notices")
    return render(
        request,
        "adminpanel/notice_form.html",
        {"form": form, "title": f"Edit Notice — {notice.title}"},
    )


@role_required("SUPER_ADMIN")
def delete_notice(request, pk):
    from academics.models import Notice

    notice = get_object_or_404(Notice, pk=pk)
    if request.method == "POST":
        notice.delete()
        messages.success(request, "Notice deleted.")
    return redirect("accounts:manage_notices")


# ---------------------------------------------------------------------------
# Super Admin — departments
# ---------------------------------------------------------------------------
@role_required("SUPER_ADMIN")
def manage_departments(request):
    from academics.models import Department

    departments = Department.objects.annotate(
        student_count=Count("students", distinct=True),
        teacher_count=Count("teachers", distinct=True),
        course_count=Count("courses", distinct=True),
    ).select_related("administrator__user")
    return render(
        request, "adminpanel/departments.html", {"departments": departments}
    )


@role_required("SUPER_ADMIN")
def add_department(request):
    form = DepartmentForm(request.POST or None)
    if form.is_valid():
        dept = form.save()
        messages.success(request, f"Department '{dept.name}' created.")
        return redirect("accounts:manage_departments")
    return render(
        request,
        "adminpanel/department_form.html",
        {
            "form": form,
            "title": "Create Department",
            "cancel_url": reverse("accounts:manage_departments"),
        },
    )


@role_required("SUPER_ADMIN")
def edit_department(request, pk):
    from academics.models import Department

    dept = get_object_or_404(Department, pk=pk)
    form = DepartmentForm(request.POST or None, instance=dept)
    if form.is_valid():
        form.save()
        messages.success(request, f"Department '{dept.name}' updated.")
        return redirect("accounts:manage_departments")
    return render(
        request,
        "adminpanel/department_form.html",
        {
            "form": form,
            "title": f"Edit Department — {dept.code}",
            "cancel_url": reverse("accounts:manage_departments"),
        },
    )


# ---------------------------------------------------------------------------
# Super Admin — department administrators
# ---------------------------------------------------------------------------
@role_required("SUPER_ADMIN")
def manage_dept_admins(request):
    admins = DepartmentAdmin.objects.select_related("user", "department")
    return render(request, "adminpanel/dept_admins.html", {"admins": admins})


@role_required("SUPER_ADMIN")
def add_dept_admin(request):
    form = DepartmentAdminCreateForm(request.POST or None)
    if form.is_valid():
        profile = form.save()
        messages.success(
            request,
            f"{profile.user.get_full_name()} is now the administrator of "
            f"{profile.department.name}. Login: {profile.user.username} / "
            f"{form.cleaned_data['password']}",
        )
        return redirect("accounts:manage_dept_admins")
    return render(
        request,
        "adminpanel/dept_admin_form.html",
        {
            "form": form,
            "title": "Create Department Administrator",
            "cancel_url": reverse("accounts:manage_dept_admins"),
        },
    )


@role_required("SUPER_ADMIN")
def edit_dept_admin(request, pk):
    profile = get_object_or_404(
        DepartmentAdmin.objects.select_related("user", "department"), pk=pk
    )
    form = DepartmentAdminUpdateForm(request.POST or None, profile=profile)
    if form.is_valid():
        form.save()
        messages.success(
            request, f"Department administrator '{profile.user.username}' updated."
        )
        return redirect("accounts:manage_dept_admins")
    return render(
        request,
        "adminpanel/dept_admin_form.html",
        {
            "form": form,
            "title": f"Edit Department Administrator — {profile.user.username}",
            "cancel_url": reverse("accounts:manage_dept_admins"),
        },
    )


@role_required("SUPER_ADMIN")
def toggle_dept_admin(request, pk):
    """Disable / re-enable a Department Administrator account."""
    profile = get_object_or_404(
        DepartmentAdmin.objects.select_related("user"), pk=pk
    )
    if request.method == "POST":
        user = profile.user
        if user.pk == request.user.pk:
            messages.error(request, "You cannot disable your own account.")
            return redirect("accounts:manage_dept_admins")
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        state = "re-enabled" if user.is_active else "disabled"
        messages.warning(
            request,
            f"Account of {user.get_full_name()} ({user.username}) {state}.",
        )
    return redirect("accounts:manage_dept_admins")


# ---------------------------------------------------------------------------
# Super Admin — all users
# ---------------------------------------------------------------------------
@role_required("SUPER_ADMIN")
def manage_users(request):
    users = User.objects.exclude(pk=request.user.pk).order_by("role", "username")
    role = request.GET.get("role", "")
    q = request.GET.get("q", "").strip()
    if role:
        users = users.filter(role=role)
    if q:
        users = users.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )
    return render(
        request,
        "adminpanel/users.html",
        {"users": users, "role": role, "q": q, "roles": User.Roles.choices},
    )


@role_required("SUPER_ADMIN")
def add_staff(request):
    """Create a central staff account (Librarian / Cashier)."""
    form = StaffUserCreateForm(request.POST or None)
    if form.is_valid():
        user = form.save()
        messages.success(
            request,
            f"{user.get_full_name()} added as {user.get_role_display()}. "
            f"Login: {user.username} / {form.cleaned_data['password']}",
        )
        return redirect(f"{reverse('accounts:manage_users')}?role={user.role}")
    return render(
        request,
        "adminpanel/staff_form.html",
        {
            "form": form,
            "title": "Add Central Staff — Librarian / Cashier",
            "cancel_url": reverse("accounts:manage_users"),
        },
    )


@role_required("SUPER_ADMIN")
def toggle_user(request, pk):
    """Disable / re-enable any user account (except superusers and yourself)."""
    target = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if target.pk == request.user.pk:
            messages.error(request, "You cannot disable your own account.")
        elif target.is_superuser:
            messages.error(request, "Superuser accounts cannot be disabled from here.")
        else:
            target.is_active = not target.is_active
            target.save(update_fields=["is_active"])
            state = "re-enabled" if target.is_active else "disabled"
            messages.warning(request, f"{target.username} {state}.")
    return redirect(
        f"{reverse('accounts:manage_users')}"
        f"?role={request.GET.get('role', '')}&q={request.GET.get('q', '')}"
    )
