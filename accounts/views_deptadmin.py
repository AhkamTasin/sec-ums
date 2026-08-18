"""Department Administrator module.

Every view is wrapped by ``dept_admin_required``, which resolves the admin's
own department and injects it as ``dept``. ALL queries below are filtered by
that department, so no administrator can ever reach another department's data
(objects outside their department simply 404).
"""

import csv
import io

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.decorators import dept_admin_required
from accounts.forms import (
    DeptAdminNoticeForm,
    StudentCreateForm,
    StudentImportForm,
    StudentUpdateForm,
    TeacherCreateForm,
    TeacherUpdateForm,
)
from accounts.models import Student, Teacher, User
from academics.forms import CourseForm, DeptRoutineForm
from academics.models import (
    Course,
    InCourseMark,
    Notice,
    Result,
    Routine,
    theory_course_grade,
)
from academics.views import visible_notices, weekly_grid

SEMESTERS = range(1, 9)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@dept_admin_required
def dept_dashboard(request, dept):
    from fees.services import student_account
    from library.models import BookIssue

    students = Student.objects.filter(department=dept)
    teachers = Teacher.objects.filter(department=dept)
    courses = Course.objects.filter(department=dept)

    total_due = 0
    for student in students.select_related("user"):
        _, _, due = student_account(student)
        if due > 0:
            total_due += due

    result_qs = Result.objects.filter(course__department=dept)
    today_name = timezone.localdate().strftime("%A")

    context = {
        "dept": dept,
        "student_count": students.count(),
        "teacher_count": teachers.count(),
        "course_count": courses.count(),
        "pending_results": result_qs.filter(is_published=False).count(),
        "published_results": result_qs.filter(is_published=True).count(),
        "total_due": total_due,
        "today_classes": Routine.objects.filter(department=dept, day=today_name).count(),
        "books_issued": BookIssue.objects.filter(
            student__department=dept, status="ISSUED"
        ).count(),
        "recent_students": students.select_related("user")[:6],
        "notices": visible_notices(request.user, limit=5),
        "pending_courses": (
            Course.objects.filter(
                department=dept,
                results__is_published=False,
            )
            .distinct()
            .annotate(pending=Count("results", filter=Q(results__is_published=False)))
            .order_by("semester", "code")[:6]
        ),
    }
    return render(request, "deptadmin/dashboard.html", context)


# ---------------------------------------------------------------------------
# Students of MY department: view / search / filter / add / edit / delete /
# import / export
# ---------------------------------------------------------------------------
def _filtered_students(request, dept):
    students = Student.objects.filter(department=dept).select_related("user")
    q = request.GET.get("q", "").strip()
    sem = request.GET.get("sem", "")
    if q:
        students = students.filter(
            Q(reg_no__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
        )
    if sem.isdigit():
        students = students.filter(semester=int(sem))
    return students, q, sem


@dept_admin_required
def dept_students(request, dept):
    students, q, sem = _filtered_students(request, dept)
    return render(
        request,
        "deptadmin/students.html",
        {"students": students, "q": q, "sem": sem, "dept": dept, "semesters": SEMESTERS},
    )


@dept_admin_required
def dept_add_student(request, dept):
    form = StudentCreateForm(request.POST or None, locked_department=dept)
    if form.is_valid():
        student = form.save()
        assert student.department_id == dept.id
        messages.success(
            request,
            f"Student {student.user.get_full_name()} ({student.reg_no}) added to "
            f"{dept.code}. Login: {student.reg_no} / {form.cleaned_data['password']}",
        )
        return redirect("accounts:dept_students")
    return render(
        request,
        "adminpanel/student_form.html",
        {
            "form": form,
            "title": f"Add Student — {dept.code}",
            "cancel_url": reverse("accounts:dept_students"),
        },
    )


@dept_admin_required
def dept_edit_student(request, dept, pk):
    # 404 if the student belongs to ANY other department
    student = get_object_or_404(
        Student.objects.select_related("user"), pk=pk, department=dept
    )
    form = StudentUpdateForm(
        request.POST or None, student=student, locked_department=dept
    )
    if form.is_valid():
        form.save()
        messages.success(request, f"Student {student.reg_no} updated.")
        return redirect("accounts:dept_students")
    return render(
        request,
        "adminpanel/student_form.html",
        {
            "form": form,
            "title": f"Edit Student — {student.reg_no}",
            "cancel_url": reverse("accounts:dept_students"),
        },
    )


@dept_admin_required
def dept_delete_student(request, dept, pk):
    student = get_object_or_404(
        Student.objects.select_related("user"), pk=pk, department=dept
    )
    if request.method == "POST":
        label = f"{student.user.get_full_name()} ({student.reg_no})"
        student.user.delete()  # cascades profile, results, payments, issues
        messages.warning(request, f"Student {label} and all related records deleted.")
    return redirect("accounts:dept_students")


@dept_admin_required
def dept_import_students(request, dept):
    form = StudentImportForm(request.POST or None, request.FILES or None)
    created, skipped = [], []

    if form.is_valid():
        upload = form.cleaned_data["csv_file"]
        try:
            wrapper = io.TextIOWrapper(upload.file, encoding="utf-8-sig")
            reader = csv.DictReader(wrapper)
        except Exception:
            messages.error(request, "Could not read the uploaded CSV file.")
            return redirect("accounts:dept_import_students")

        for line_no, row in enumerate(reader, start=2):  # row 1 = header
            reg_no = (row.get("reg_no") or "").strip()
            first = (row.get("first_name") or "").strip()
            last = (row.get("last_name") or "").strip()
            sem_raw = (row.get("semester") or "").strip()
            session = (row.get("session") or "").strip()

            if not (reg_no and first and session and sem_raw.isdigit()):
                skipped.append((line_no, reg_no or "—", "missing required fields"))
                continue
            semester = int(sem_raw)
            if not 1 <= semester <= 8:
                skipped.append((line_no, reg_no, "semester must be 1-8"))
                continue
            if (
                Student.objects.filter(reg_no=reg_no).exists()
                or User.objects.filter(username=reg_no).exists()
            ):
                skipped.append((line_no, reg_no, "registration no already exists"))
                continue

            gender = (row.get("gender") or "M").strip().upper()[:1]
            if gender not in ("M", "F", "O"):
                gender = "M"
            password = (row.get("password") or "").strip() or "student123"

            with transaction.atomic():
                user = User.objects.create_user(
                    username=reg_no,
                    password=password,
                    first_name=first,
                    last_name=last,
                    email=(row.get("email") or "").strip(),
                    phone=(row.get("phone") or "").strip(),
                    role=User.Roles.STUDENT,
                )
                student = Student.objects.create(
                    user=user,
                    reg_no=reg_no,
                    department=dept,  # always the admin's own department
                    semester=semester,
                    session=session,
                    gender=gender,
                    guardian_name=(row.get("guardian_name") or "").strip(),
                    guardian_phone=(row.get("guardian_phone") or "").strip(),
                )
            created.append(student)

        if created:
            messages.success(
                request, f"Imported {len(created)} student(s) into {dept.code}."
            )
        if skipped:
            messages.warning(
                request, f"Skipped {len(skipped)} row(s) — see details below."
            )

    return render(
        request,
        "deptadmin/student_import.html",
        {"form": form, "created": created, "skipped": skipped, "dept": dept},
    )


@dept_admin_required
def dept_export_students(request, dept):
    students, _, _ = _filtered_students(request, dept)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="students_{dept.code}_{timezone.localdate():%Y%m%d}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(
        [
            "reg_no", "first_name", "last_name", "email", "phone",
            "department", "semester", "session", "gender",
            "guardian_name", "guardian_phone",
        ]
    )
    for s in students:
        writer.writerow(
            [
                s.reg_no, s.user.first_name, s.user.last_name, s.user.email,
                s.user.phone, dept.code, s.semester, s.session, s.gender,
                s.guardian_name, s.guardian_phone,
            ]
        )
    return response


# ---------------------------------------------------------------------------
# Semester management (promote student batches)
# ---------------------------------------------------------------------------
@dept_admin_required
def dept_semesters(request, dept):
    rows = [
        {
            "semester": sem,
            "count": Student.objects.filter(department=dept, semester=sem).count(),
        }
        for sem in SEMESTERS
    ]
    return render(
        request, "deptadmin/semesters.html", {"rows": rows, "dept": dept}
    )


@dept_admin_required
def dept_promote_semester(request, dept):
    if request.method == "POST":
        sem_raw = request.POST.get("from_semester", "")
        if sem_raw.isdigit() and 1 <= int(sem_raw) < 8:
            src = int(sem_raw)
            updated = Student.objects.filter(
                department=dept, semester=src
            ).update(semester=src + 1)
            messages.success(
                request,
                f"Promoted {updated} student(s) from Semester {src} to {src + 1}.",
            )
        else:
            messages.error(request, "Invalid semester for promotion.")
    return redirect("accounts:dept_semesters")


# ---------------------------------------------------------------------------
# Teachers of MY department: view / add / edit / delete
# ---------------------------------------------------------------------------
@dept_admin_required
def dept_teachers(request, dept):
    q = request.GET.get("q", "").strip()
    teachers = Teacher.objects.filter(department=dept).select_related("user")
    if q:
        teachers = teachers.filter(
            Q(employee_id__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
        )
    return render(
        request,
        "deptadmin/teachers.html",
        {"teachers": teachers, "q": q, "dept": dept},
    )


@dept_admin_required
def dept_add_teacher(request, dept):
    form = TeacherCreateForm(request.POST or None, locked_department=dept)
    if form.is_valid():
        teacher = form.save()
        assert teacher.department_id == dept.id
        messages.success(
            request,
            f"Teacher {teacher.user.get_full_name()} ({teacher.employee_id}) added "
            f"to {dept.code}. Login: {teacher.employee_id} / "
            f"{form.cleaned_data['password']}",
        )
        return redirect("accounts:dept_teachers")
    return render(
        request,
        "adminpanel/teacher_form.html",
        {
            "form": form,
            "title": f"Add Teacher — {dept.code}",
            "cancel_url": reverse("accounts:dept_teachers"),
        },
    )


@dept_admin_required
def dept_edit_teacher(request, dept, pk):
    # 404 if the teacher belongs to ANY other department
    teacher = get_object_or_404(
        Teacher.objects.select_related("user"), pk=pk, department=dept
    )
    form = TeacherUpdateForm(
        request.POST or None, teacher=teacher, locked_department=dept
    )
    if form.is_valid():
        form.save()
        messages.success(request, f"Teacher {teacher.employee_id} updated.")
        return redirect("accounts:dept_teachers")
    return render(
        request,
        "adminpanel/teacher_form.html",
        {
            "form": form,
            "title": f"Update Teacher — {teacher.employee_id}",
            "cancel_url": reverse("accounts:dept_teachers"),
        },
    )


@dept_admin_required
def dept_delete_teacher(request, dept, pk):
    teacher = get_object_or_404(
        Teacher.objects.select_related("user"), pk=pk, department=dept
    )
    if request.method == "POST":
        label = f"{teacher.user.get_full_name()} ({teacher.employee_id})"
        teacher.user.delete()  # courses/routines keep their data (teacher -> NULL)
        messages.warning(request, f"Teacher {label} deleted.")
    return redirect("accounts:dept_teachers")


# ---------------------------------------------------------------------------
# Courses of MY department (create / assign teachers / semester field)
# ---------------------------------------------------------------------------
@dept_admin_required
def dept_courses(request, dept):
    courses = Course.objects.filter(department=dept).select_related(
        "teacher__user"
    )
    return render(
        request, "deptadmin/courses.html", {"courses": courses, "dept": dept}
    )


@dept_admin_required
def dept_add_course(request, dept):
    form = CourseForm(request.POST or None, locked_department=dept)
    if form.is_valid():
        course = form.save(commit=False)
        course.department = dept  # hard-assigned, never from the request
        course.save()
        messages.success(request, f"Course {course.code} — {course.title} created.")
        return redirect("accounts:dept_courses")
    return render(
        request,
        "deptadmin/course_form.html",
        {
            "form": form,
            "title": f"Add Course — {dept.code}",
            "cancel_url": reverse("accounts:dept_courses"),
        },
    )


@dept_admin_required
def dept_edit_course(request, dept, pk):
    # 404 if the course belongs to ANY other department
    course = get_object_or_404(Course, pk=pk, department=dept)
    form = CourseForm(
        request.POST or None, instance=course, locked_department=dept
    )
    if form.is_valid():
        obj = form.save(commit=False)
        obj.department = dept
        obj.save()
        messages.success(request, f"Course {course.code} updated.")
        return redirect("accounts:dept_courses")
    return render(
        request,
        "deptadmin/course_form.html",
        {
            "form": form,
            "title": f"Edit Course — {course.code}",
            "cancel_url": reverse("accounts:dept_courses"),
        },
    )


# ---------------------------------------------------------------------------
# Routine of MY department: view / create / update / delete
# ---------------------------------------------------------------------------
@dept_admin_required
def dept_routine(request, dept):
    sem = request.GET.get("sem")
    routines = Routine.objects.filter(department=dept).select_related(
        "course", "teacher__user"
    )
    if sem and sem.isdigit():
        sem = int(sem)
        routines = routines.filter(semester=sem)
    else:
        sem = None
    return render(
        request,
        "deptadmin/routine.html",
        {
            "dept": dept,
            "grid": weekly_grid(routines),
            "sem": sem,
            "semesters": SEMESTERS,
        },
    )


@dept_admin_required
def dept_add_routine(request, dept):
    form = DeptRoutineForm(request.POST or None, department=dept)
    if form.is_valid():
        slot = form.save()
        messages.success(request, f"Class scheduled: {slot}.")
        return redirect("accounts:dept_routine")
    return render(
        request,
        "deptadmin/course_form.html",
        {
            "form": form,
            "title": f"Schedule Class — {dept.code}",
            "cancel_url": reverse("accounts:dept_routine"),
        },
    )


@dept_admin_required
def dept_edit_routine(request, dept, pk):
    slot = get_object_or_404(Routine, pk=pk, department=dept)
    form = DeptRoutineForm(request.POST or None, instance=slot, department=dept)
    if form.is_valid():
        form.save()
        messages.success(request, "Class slot updated.")
        return redirect("accounts:dept_routine")
    return render(
        request,
        "deptadmin/course_form.html",
        {
            "form": form,
            "title": f"Edit Class Slot — {slot.course.code}",
            "cancel_url": reverse("accounts:dept_routine"),
        },
    )


@dept_admin_required
def dept_delete_routine(request, dept, pk):
    slot = get_object_or_404(Routine, pk=pk, department=dept)
    if request.method == "POST":
        slot.delete()
        messages.warning(request, "Class slot removed.")
    return redirect("accounts:dept_routine")


# ---------------------------------------------------------------------------
# Notices of MY department: publish / edit / delete
# ---------------------------------------------------------------------------
@dept_admin_required
def dept_notices(request, dept):
    notices = Notice.objects.filter(department=dept).select_related("created_by")
    return render(
        request, "deptadmin/notices.html", {"notices": notices, "dept": dept}
    )


@dept_admin_required
def dept_add_notice(request, dept):
    form = DeptAdminNoticeForm(request.POST or None)
    if form.is_valid():
        notice = form.save(commit=False)
        notice.department = dept  # always scoped to the admin's department
        notice.created_by = request.user
        notice.save()
        messages.success(request, "Notice published to your department.")
        return redirect("accounts:dept_notices")
    return render(
        request,
        "deptadmin/course_form.html",
        {
            "form": form,
            "title": f"Publish Notice — {dept.code}",
            "cancel_url": reverse("accounts:dept_notices"),
        },
    )


@dept_admin_required
def dept_edit_notice(request, dept, pk):
    notice = get_object_or_404(Notice, pk=pk, department=dept)
    form = DeptAdminNoticeForm(request.POST or None, instance=notice)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.department = dept
        obj.save()
        messages.success(request, "Notice updated.")
        return redirect("accounts:dept_notices")
    return render(
        request,
        "deptadmin/course_form.html",
        {
            "form": form,
            "title": f"Edit Notice — {notice.title}",
            "cancel_url": reverse("accounts:dept_notices"),
        },
    )


@dept_admin_required
def dept_delete_notice(request, dept, pk):
    notice = get_object_or_404(Notice, pk=pk, department=dept)
    if request.method == "POST":
        notice.delete()
        messages.warning(request, "Notice deleted.")
    return redirect("accounts:dept_notices")


# ---------------------------------------------------------------------------
# Results: review teachers' submitted marks, publish / unpublish
# ---------------------------------------------------------------------------
@dept_admin_required
def dept_results(request, dept):
    enrolled_map = dict(
        Student.objects.filter(department=dept)
        .values_list("semester")
        .annotate(n=Count("id"))
        .values_list("semester", "n")
    )
    courses = (
        Course.objects.filter(department=dept)
        .annotate(
            final_count=Count("results", filter=Q(results__exam_type="FINAL")),
            final_published=Count(
                "results",
                filter=Q(results__exam_type="FINAL", results__is_published=True),
            ),
            incourse_count=Count("incourse_marks"),
        )
        .select_related("teacher__user")
    )
    rows = [
        {"course": c, "enrolled": enrolled_map.get(c.semester, 0)} for c in courses
    ]
    return render(
        request, "deptadmin/results.html", {"rows": rows, "dept": dept}
    )


def _exam_label(exam_type):
    return "Midterm" if exam_type == "MID" else "Final"


@dept_admin_required
def dept_results_review(request, dept, course_id, exam_type):
    course = get_object_or_404(Course, pk=course_id, department=dept)
    if exam_type != "FINAL":
        messages.error(request, "Publication is done for final course results.")
        return redirect("accounts:dept_results")
    existing = {
        r.student_id: r
        for r in Result.objects.filter(course=course, exam_type="FINAL")
    }
    students = Student.objects.filter(
        department=dept, semester=course.semester, user__is_active=True
    ).select_related("user")
    incourse = {}
    if not course.is_lab:
        incourse = {
            m.student_id: m for m in InCourseMark.objects.filter(course=course)
        }
    rows = []
    for s in students:
        result = existing.get(s.id)
        ic = incourse.get(s.id)
        combined = None
        if result and ic and not course.is_lab:
            grade, point = theory_course_grade(ic.total, result.marks)
            combined = {
                "total": round(float(ic.total) + float(result.marks), 2),
                "grade": grade,
                "point": point,
            }
        rows.append(
            {"student": s, "result": result, "incourse": ic, "combined": combined}
        )
    published = bool(existing) and all(r.is_published for r in existing.values())
    missing_incourse = 0
    if not course.is_lab:
        missing_incourse = sum(1 for r in rows if r["incourse"] is None)
    return render(
        request,
        "deptadmin/results_review.html",
        {
            "dept": dept,
            "course": course,
            "exam_type": exam_type,
            "exam_label": _exam_label(exam_type),
            "rows": rows,
            "published": published,
            "submitted": len(existing),
            "missing_incourse": missing_incourse,
        },
    )


@dept_admin_required
def dept_results_publish(request, dept, course_id, exam_type, action):
    """Only the Department Administrator can publish semester results."""
    course = get_object_or_404(Course, pk=course_id, department=dept)
    if (
        request.method == "POST"
        and exam_type == "FINAL"
        and action in ("publish", "unpublish")
    ):
        qs = Result.objects.filter(course=course, exam_type="FINAL")
        if action == "publish":
            if not qs.exists():
                messages.error(request, "Nothing to publish — no marks submitted yet.")
            else:
                if not course.is_lab:
                    # in-course (40) must be submitted for every enrolled student
                    enrolled = set(
                        Student.objects.filter(
                            department=dept,
                            semester=course.semester,
                            user__is_active=True,
                        ).values_list("id", flat=True)
                    )
                    have_ic = set(
                        InCourseMark.objects.filter(course=course).values_list(
                            "student_id", flat=True
                        )
                    )
                    missing = len(enrolled - have_ic)
                    if missing:
                        messages.error(
                            request,
                            f"Cannot publish yet — in-course marks (/40) are not "
                            f"submitted for {missing} student(s). Ask the course "
                            f"teacher to submit in-course marks first.",
                        )
                        return redirect(
                            "accounts:dept_results_review",
                            course_id=course.id,
                            exam_type=exam_type,
                        )
                    # stamp combined grade (in-course 40 + final 60) on each row
                    ic_map = {
                        m.student_id: m.total
                        for m in InCourseMark.objects.filter(course=course)
                    }
                    for r in qs:
                        total_inc = ic_map.get(r.student_id)
                        if total_inc is None:
                            continue
                        r.grade, r.grade_point = theory_course_grade(
                            total_inc, r.marks
                        )
                        r.is_published = True
                        r.published_at = timezone.now()
                        r.published_by = request.user
                        r.save(update_fields=[
                            "grade", "grade_point", "is_published",
                            "published_at", "published_by",
                        ])
                    n = qs.filter(is_published=True).count()
                else:
                    n = qs.update(
                        is_published=True,
                        published_at=timezone.now(),
                        published_by=request.user,
                    )
                messages.success(
                    request,
                    f"Published {n} final result(s) for {course.code}. "
                    f"Students can now see them.",
                )
        else:
            n = qs.update(is_published=False, published_at=None, published_by=None)
            messages.warning(
                request,
                f"Unpublished {n} final result(s) for {course.code}. "
                f"They are hidden from students again.",
            )
        return redirect(
            "accounts:dept_results_review", course_id=course.id, exam_type=exam_type
        )
    return redirect("accounts:dept_results")
