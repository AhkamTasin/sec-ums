"""Views for the Student module, Teacher module and shared notices."""

from datetime import datetime
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.decorators import role_required
from accounts.models import Student

from .forms import AssessmentForm, CourseMaterialForm, RoutineForm
from .models import (
    Assessment,
    AssessmentMark,
    Attendance,
    Course,
    CourseMaterial,
    InCourseMark,
    Notice,
    Result,
    Routine,
    compute_incourse,
)

WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def visible_notices(user, limit=None):
    """Notices a user may see: role-audience match AND scope match.

    Scope rules — global notices (department=NULL) are visible to everyone;
    department notices only to users belonging to that department
    (students/teachers via their profile, dept admins via their managed
    department). Librarians/cashiers/super admins see global notices here
    (the super admin manages all notices from their own panel).
    """
    qs = Notice.objects.filter(Q(audience="ALL") | Q(audience=user.role))
    dept = None
    if user.is_authenticated:
        if user.role == "STUDENT":
            dept = user.student_profile.department
        elif user.role == "TEACHER":
            dept = user.teacher_profile.department
        elif user.role == "DEPT_ADMIN":
            dept = user.managed_department
    if dept is not None:
        qs = qs.filter(Q(department__isnull=True) | Q(department=dept))
    else:
        qs = qs.filter(department__isnull=True)
    return qs[:limit] if limit else qs


def compute_transcript(student, exam_type="FINAL"):
    """Group PUBLISHED results by semester, GPA per semester + CGPA.

    This helper is only used by student-facing pages, so it always hides
    results the Department Administrator has not published yet.
    """
    results = (
        Result.objects.filter(student=student, exam_type=exam_type, is_published=True)
        .select_related("course")
        .order_by("course__semester", "course__code")
    )
    semesters = {}
    for r in results:
        bucket = semesters.setdefault(
            r.course.semester, {"results": [], "credits": 0.0, "points": 0.0}
        )
        credit = float(r.course.credit)
        bucket["results"].append(r)
        bucket["credits"] += credit
        bucket["points"] += credit * float(r.grade_point)

    rows = []
    total_credits = total_points = 0.0
    for sem in sorted(semesters):
        data = semesters[sem]
        gpa = data["points"] / data["credits"] if data["credits"] else 0.0
        rows.append({"semester": sem, "gpa": round(gpa, 2), **data})
        total_credits += data["credits"]
        total_points += data["points"]

    cgpa = round(total_points / total_credits, 2) if total_credits else None
    return rows, cgpa, total_credits


def weekly_grid(routines):
    """Return [(day, [slots...]), ...] in week order (templates can't do dynamic dict keys)."""
    grid = {day: [] for day in WEEKDAYS}
    for slot in routines:
        grid[slot.day].append(slot)
    return [(day, grid[day]) for day in WEEKDAYS]


# ---------------------------------------------------------------------------
# Shared notices page (all roles)
# ---------------------------------------------------------------------------
@login_required
def notices_view(request):
    return render(
        request, "notices.html", {"notices": visible_notices(request.user)}
    )


# ---------------------------------------------------------------------------
# Student module
# ---------------------------------------------------------------------------
@role_required("STUDENT")
def student_dashboard(request):
    from fees.services import student_account
    from library.models import BookIssue

    student = request.user.student_profile
    _, cgpa, _ = compute_transcript(student)
    payable, paid, due = student_account(student)
    today_name = timezone.localdate().strftime("%A")

    # Overall attendance percentage (present + late counts as attended)
    att_qs = Attendance.objects.filter(student=student)
    att_total = att_qs.count()
    att_pct = (
        round(att_qs.exclude(status="ABSENT").count() / att_total * 100, 1)
        if att_total
        else None
    )

    # Upcoming exams & deadlines: future-dated assessments of my courses
    upcoming = (
        Assessment.objects.filter(
            course__department=student.department,
            course__semester=student.semester,
            due_date__gte=timezone.localdate(),
        )
        .select_related("course")
        .order_by("due_date")[:6]
    )

    context = {
        "student": student,
        "cgpa": cgpa,
        "att_pct": att_pct,
        "due": due if due > 0 else 0,
        "paid": paid,
        "books_issued": BookIssue.objects.filter(student=student, status="ISSUED").count(),
        "notices": visible_notices(request.user, limit=5),
        "upcoming": upcoming,
        "today_classes": Routine.objects.filter(
            department=student.department, semester=student.semester, day=today_name
        ).select_related("course", "teacher__user"),
    }
    return render(request, "student/dashboard.html", context)


@role_required("STUDENT")
def student_results(request):
    student = request.user.student_profile
    final_rows, cgpa, total_credits = compute_transcript(student, "FINAL")
    midterm_results = (
        Result.objects.filter(student=student, exam_type="MID", is_published=True)
        .select_related("course")
        .order_by("course__semester", "course__code")
    )
    context = {
        "student": student,
        "final_rows": final_rows,
        "cgpa": cgpa,
        "total_credits": total_credits,
        "midterm_results": midterm_results,
    }
    return render(request, "student/results.html", context)


@role_required("STUDENT")
def student_routine(request):
    student = request.user.student_profile
    routines = Routine.objects.filter(
        department=student.department, semester=student.semester
    ).select_related("course", "teacher__user")
    return render(
        request,
        "student/routine.html",
        {"student": student, "grid": weekly_grid(routines), "days": WEEKDAYS},
    )


@role_required("STUDENT")
def student_fees(request):
    from fees.models import FeeStructure, Payment
    from fees.services import student_account

    student = request.user.student_profile
    structures = FeeStructure.objects.filter(
        department=student.department, semester__lte=student.semester
    )
    payments = Payment.objects.filter(student=student)
    payable, paid, due = student_account(student)
    return render(
        request,
        "student/fees.html",
        {
            "student": student,
            "structures": structures,
            "payments": payments,
            "payable": payable,
            "paid": paid,
            "due": due,
        },
    )


# ---------------------------------------------------------------------------
# Teacher module
# ---------------------------------------------------------------------------
@role_required("TEACHER")
def teacher_dashboard(request):
    teacher = request.user.teacher_profile
    courses = teacher.courses.select_related("department")
    today_name = timezone.localdate().strftime("%A")
    course_rows = [
        {
            "course": course,
            "students": Student.objects.filter(
                department=course.department, semester=course.semester
            ).count(),
        }
        for course in courses
    ]
    context = {
        "teacher": teacher,
        "course_rows": course_rows,
        "total_students": sum(r["students"] for r in course_rows),
        "today_classes": Routine.objects.filter(
            teacher=teacher, day=today_name
        ).select_related("course"),
        "notices": visible_notices(request.user, limit=5),
    }
    return render(request, "teacher/dashboard.html", context)


@role_required("TEACHER")
def teacher_results_courses(request):
    teacher = request.user.teacher_profile
    courses = teacher.courses.select_related("department")
    return render(request, "teacher/results_courses.html", {"courses": courses})


def _results_sheet(request, course_id, exam_type):
    """Shared loader: course + enrolled students + existing marks."""
    if exam_type not in ("MID", "FINAL"):
        messages.error(request, "Unknown exam type.")
        return None
    course = get_object_or_404(Course.objects.select_related("department"), pk=course_id)
    if request.user.role == "TEACHER":
        teacher = request.user.teacher_profile
        if course.teacher_id != teacher.id:
            return None
    students = Student.objects.filter(
        department=course.department, semester=course.semester, user__is_active=True
    ).select_related("user")
    existing = {
        r.student_id: r
        for r in Result.objects.filter(course=course, exam_type=exam_type)
    }
    return course, students, existing


@role_required("TEACHER")
def teacher_results_entry(request, course_id, exam_type):
    loaded = _results_sheet(request, course_id, exam_type)
    if not loaded:
        messages.error(request, "You are not assigned to this course/exam.")
        return redirect("academics:teacher_results_courses")
    course, students, existing = loaded

    published = any(r.is_published for r in existing.values())

    if request.method == "POST":
        if published:
            messages.error(
                request,
                "These results have already been published by the Department "
                "Administrator and are locked. Contact them to unpublish first.",
            )
            return redirect(
                "academics:teacher_results_entry",
                course_id=course.id,
                exam_type=exam_type,
            )
        saved = 0
        for student in students:
            raw = request.POST.get(f"marks_{student.id}", "").strip()
            if raw == "":
                continue
            try:
                marks = float(raw)
            except ValueError:
                messages.error(request, f"Invalid marks for {student.reg_no}.")
                continue
            if not 0 <= marks <= 100:
                messages.error(request, f"Marks for {student.reg_no} must be 0–100.")
                continue
            Result.objects.update_or_create(
                student=student,
                course=course,
                exam_type=exam_type,
                defaults={"marks": marks},
            )
            saved += 1
        messages.success(request, f"Saved marks for {saved} student(s).")
        return redirect(
            "academics:teacher_results_entry",
            course_id=course.id,
            exam_type=exam_type,
        )

    rows = [{"student": s, "result": existing.get(s.id)} for s in students]
    return render(
        request,
        "teacher/results_entry.html",
        {"course": course, "exam_type": exam_type, "rows": rows, "published": published},
    )


@role_required("TEACHER", "ADMIN")
def teacher_results_print(request, course_id, exam_type):
    loaded = _results_sheet(request, course_id, exam_type)
    if not loaded:
        messages.error(request, "No result sheet available.")
        return redirect("academics:teacher_results_courses")
    course, students, existing = loaded
    rows = [{"student": s, "result": existing.get(s.id)} for s in students]
    return render(
        request,
        "teacher/results_print.html",
        {"course": course, "exam_type": exam_type, "rows": rows},
    )


@role_required("TEACHER")
def teacher_routine(request):
    teacher = request.user.teacher_profile
    form = RoutineForm(request.POST or None, teacher=teacher)
    if request.method == "POST" and form.is_valid():
        slot = form.save()
        messages.success(request, f"Class scheduled: {slot}.")
        return redirect("academics:teacher_routine")
    routines = teacher.routines.select_related("course", "department")
    return render(
        request,
        "teacher/routine.html",
        {
            "teacher": teacher,
            "form": form,
            "grid": weekly_grid(routines),
            "days": WEEKDAYS,
        },
    )


@role_required("TEACHER")
def teacher_routine_delete(request, pk):
    teacher = request.user.teacher_profile
    slot = get_object_or_404(Routine, pk=pk, teacher=teacher)
    if request.method == "POST":
        slot.delete()
        messages.success(request, "Class slot removed.")
    return redirect("academics:teacher_routine")


# ===========================================================================
# Teacher module — assigned students
# ===========================================================================
def _own_course(request, course_id):
    """404 when the course is not taught by the current teacher."""
    return get_object_or_404(Course, pk=course_id, teacher=request.user.teacher_profile)


@role_required("TEACHER")
def teacher_course_students(request, course_id):
    course = _own_course(request, course_id)
    students = Student.objects.filter(
        department=course.department, semester=course.semester
    ).select_related("user")
    return render(
        request,
        "teacher/course_students.html",
        {"course": course, "students": students},
    )


# ===========================================================================
# Teacher module — attendance management
# ===========================================================================
ATTENDANCE_STATUSES = ["PRESENT", "ABSENT", "LATE"]


@role_required("TEACHER")
def teacher_attendance(request):
    teacher = request.user.teacher_profile
    courses = teacher.courses.select_related("department")

    date_str = request.POST.get("date") or request.GET.get("date") or ""
    try:
        att_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        att_date = timezone.localdate()

    course = None
    students = []
    existing = {}
    stats = []

    course_id = request.POST.get("course") or request.GET.get("course")
    if not course_id and len(courses) == 1:
        course_id = courses[0].id

    if course_id:
        course = _own_course(request, course_id)
        students = list(
            Student.objects.filter(
                department=course.department,
                semester=course.semester,
                user__is_active=True,
            ).select_related("user")
        )
        existing = {
            a.student_id: a.status
            for a in Attendance.objects.filter(course=course, date=att_date)
        }

        if request.method == "POST" and request.POST.get("save_attendance"):
            saved = 0
            for s in students:
                status = request.POST.get(f"att_{s.id}", "")
                if status not in ATTENDANCE_STATUSES:
                    continue
                Attendance.objects.update_or_create(
                    course=course, student=s, date=att_date,
                    defaults={"status": status},
                )
                saved += 1
            messages.success(
                request,
                f"Attendance saved for {saved} student(s) — "
                f"{course.code}, {att_date:%d %b %Y}.",
            )
            return redirect(
                f"{reverse('academics:teacher_attendance')}"
                f"?course={course.id}&date={att_date:%Y-%m-%d}"
            )

        # per-student attendance summary for this course
        for s in students:
            qs = Attendance.objects.filter(course=course, student=s)
            total = qs.count()
            if total:
                attended = qs.exclude(status="ABSENT").count()
                pct = round(attended / total * 100, 1)
            else:
                attended, pct = 0, None
            stats.append(
                {
                    "student": s,
                    "total": total,
                    "attended": attended,
                    "pct": pct,
                    "status": existing.get(s.id, "PRESENT"),
                }
            )

    return render(
        request,
        "teacher/attendance.html",
        {
            "courses": courses,
            "course": course,
            "att_date": att_date,
            "students": students,
            "existing": existing,
            "stats": stats,
        },
    )


# ===========================================================================
# Teacher module — course materials upload
# ===========================================================================
@role_required("TEACHER")
def teacher_materials(request):
    teacher = request.user.teacher_profile
    form = CourseMaterialForm(
        request.POST or None, request.FILES or None, teacher=teacher
    )
    if request.method == "POST" and form.is_valid():
        material = form.save(commit=False)
        material.uploaded_by = request.user
        material.save()
        messages.success(request, f"Material '{material.title}' uploaded.")
        return redirect("academics:teacher_materials")
    materials = CourseMaterial.objects.filter(
        course__teacher=teacher
    ).select_related("course")
    return render(
        request, "teacher/materials.html", {"form": form, "materials": materials}
    )


@role_required("TEACHER")
def teacher_material_delete(request, pk):
    material = get_object_or_404(
        CourseMaterial, pk=pk, course__teacher=request.user.teacher_profile
    )
    if request.method == "POST":
        material.file.delete(save=False)
        material.delete()
        messages.warning(request, "Material deleted.")
    return redirect("academics:teacher_materials")


# ===========================================================================
# Teacher module — assessments (quiz / assignment / lab) + marks entry
# ===========================================================================
@role_required("TEACHER")
def teacher_assessments(request):
    teacher = request.user.teacher_profile
    kind = request.GET.get("kind", "")
    form = AssessmentForm(request.POST or None, request.FILES or None, teacher=teacher)
    if request.method == "POST" and form.is_valid():
        assessment = form.save()
        messages.success(
            request, f"{assessment.get_kind_display()} '{assessment.title}' created."
        )
        return redirect(
            f"{reverse('academics:teacher_assessments')}?kind={assessment.kind}"
        )
    assessments = (
        Assessment.objects.filter(course__teacher=teacher)
        .select_related("course")
        .annotate(mark_count=Count("marks"))
    )
    if kind in ("QUIZ", "ASSIGNMENT", "LAB"):
        assessments = assessments.filter(kind=kind)
    return render(
        request,
        "teacher/assessments.html",
        {"form": form, "assessments": assessments, "kind": kind},
    )


@role_required("TEACHER")
def teacher_assessment_delete(request, pk):
    assessment = get_object_or_404(
        Assessment, pk=pk, course__teacher=request.user.teacher_profile
    )
    if request.method == "POST":
        assessment.delete()
        messages.warning(request, "Assessment deleted.")
    return redirect("academics:teacher_assessments")


@role_required("TEACHER")
def teacher_assessment_marks(request, pk):
    assessment = get_object_or_404(
        Assessment.objects.select_related("course", "course__department"),
        pk=pk,
        course__teacher=request.user.teacher_profile,
    )
    students = Student.objects.filter(
        department=assessment.course.department,
        semester=assessment.course.semester,
        user__is_active=True,
    ).select_related("user")
    existing = {m.student_id: m for m in assessment.marks.all()}
    max_marks = float(assessment.max_marks)

    if request.method == "POST":
        saved = 0
        for s in students:
            raw = request.POST.get(f"marks_{s.id}", "").strip()
            if raw == "":
                continue
            try:
                marks = float(raw)
            except ValueError:
                messages.error(request, f"Invalid marks for {s.reg_no}.")
                continue
            if not 0 <= marks <= max_marks:
                messages.error(
                    request, f"Marks for {s.reg_no} must be 0–{max_marks:g}."
                )
                continue
            AssessmentMark.objects.update_or_create(
                assessment=assessment, student=s, defaults={"marks": marks}
            )
            saved += 1
        messages.success(request, f"Saved marks for {saved} student(s).")
        return redirect("academics:teacher_assessment_marks", pk=assessment.pk)

    rows = [{"student": s, "mark": existing.get(s.id)} for s in students]
    return render(
        request,
        "teacher/assessment_marks.html",
        {"assessment": assessment, "rows": rows, "max_marks": max_marks},
    )


# ===========================================================================
# Teacher module — calculate & submit in-course marks
# ===========================================================================
@role_required("TEACHER")
def teacher_incourse(request, course_id):
    course = _own_course(request, course_id)
    students = Student.objects.filter(
        department=course.department, semester=course.semester, user__is_active=True
    ).select_related("user")

    if request.method == "POST":
        count = 0
        for s in students:
            calc = compute_incourse(course, s)
            InCourseMark.objects.update_or_create(
                course=course,
                student=s,
                defaults={
                    **calc,
                    "submitted_by": request.user,
                    "submitted_at": timezone.now(),
                },
            )
            count += 1
        messages.success(
            request,
            f"In-course marks submitted for {count} student(s) in {course.code}. "
            f"Students can now see them.",
        )
        return redirect("academics:teacher_incourse", course_id=course.id)

    submitted_map = {
        m.student_id: m
        for m in InCourseMark.objects.filter(course=course).select_related(
            "submitted_by"
        )
    }
    rows = [
        {
            "student": s,
            "calc": compute_incourse(course, s),
            "submitted": submitted_map.get(s.id),
        }
        for s in students
    ]
    return render(
        request,
        "teacher/incourse.html",
        {"course": course, "rows": rows},
    )


# ===========================================================================
# Student module — profile, attendance, assignments, in-course marks, PDF
# ===========================================================================
@role_required("STUDENT")
def student_profile(request):
    from accounts.forms import StudentSelfEditForm

    student = request.user.student_profile
    form = StudentSelfEditForm(request.POST or None, student=student)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("academics:student_profile")
    return render(request, "student/profile.html", {"student": student, "form": form})


@role_required("STUDENT")
def student_attendance(request):
    student = request.user.student_profile
    courses = Course.objects.filter(
        department=student.department, semester=student.semester
    )
    rows = []
    for course in courses:
        qs = Attendance.objects.filter(course=course, student=student)
        total = qs.count()
        if total:
            present = qs.filter(status="PRESENT").count()
            late = qs.filter(status="LATE").count()
            absent = total - present - late
            rows.append(
                {
                    "course": course,
                    "total": total,
                    "present": present,
                    "late": late,
                    "absent": absent,
                    "pct": round((present + late) / total * 100, 1),
                }
            )
    recent = (
        Attendance.objects.filter(student=student)
        .select_related("course")
        .order_by("-date")[:10]
    )
    return render(
        request,
        "student/attendance.html",
        {"student": student, "rows": rows, "recent": recent},
    )


def _student_courses(student):
    return Course.objects.filter(
        department=student.department, semester=student.semester
    )


@role_required("STUDENT")
def student_assignments(request):
    student = request.user.student_profile
    today = timezone.localdate()
    assessments = (
        Assessment.objects.filter(course__in=_student_courses(student))
        .select_related("course", "course__teacher__user")
        .prefetch_related("marks")
        .order_by("due_date", "date_assigned")
    )
    cards = []
    for a in assessments:
        my = next((m for m in a.marks.all() if m.student_id == student.id), None)
        cards.append(
            {
                "a": a,
                "my": my,
                "overdue": bool(a.due_date and a.due_date < today and not my),
            }
        )
    return render(
        request, "student/assignments.html", {"student": student, "cards": cards}
    )


@role_required("STUDENT")
def student_incourse(request):
    student = request.user.student_profile
    marks = (
        InCourseMark.objects.filter(student=student, course__in=_student_courses(student))
        .select_related("course", "submitted_by")
        .order_by("course__code")
    )
    return render(
        request, "student/incourse.html", {"student": student, "marks": marks}
    )


@role_required("STUDENT")
def student_results_pdf(request):
    """Download an official-looking transcript PDF (published finals only)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    student = request.user.student_profile
    rows, cgpa, total_credits = compute_transcript(student, "FINAL")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=1.6 * cm, bottomMargin=1.6 * cm
    )
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#6b7280"))
    MAROON = colors.HexColor("#701020")
    NAVY = colors.HexColor("#111b4d")

    # ---- SEC-branded letterhead (logo + institution + document title) ----
    from reportlab.platypus import Image as RLImage

    logo_path = settings.BASE_DIR / "static" / "img" / "logo.png"
    brand_style = ParagraphStyle(
        "brand", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=15, textColor=MAROON, leading=18,
    )
    brand_sub = ParagraphStyle(
        "brandSub", parent=small, fontSize=7.5, textColor=NAVY, leading=10,
    )
    logo = RLImage(str(logo_path), width=1.7 * cm, height=1.7 * cm)
    header = Table(
        [[logo,
          [Paragraph("Sylhet Engineering College", brand_style),
           Paragraph("UNIVERSITY MANAGEMENT SYSTEM", brand_sub)]],
         ["", Paragraph("<b>Official Semester Transcript (Final Results)</b>",
                        ParagraphStyle("dt", parent=styles["Normal"], fontSize=9, textColor=NAVY))]],
        colWidths=[2.1 * cm, 14 * cm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("SPAN", (0, 0), (0, 1)),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LINEBELOW", (0, 1), (-1, 1), 1.4, MAROON),
            ]
        )
    )
    elements = [
        header,
        Spacer(1, 12),
        Paragraph(
            f"<b>{student.user.get_full_name()}</b> · Reg No: {student.reg_no}<br/>"
            f"{student.department.name} · Semester {student.semester} · Session {student.session}",
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]

    for row in rows:
        data = [["Course", "Credit", "Marks", "Grade", "Point"]]
        for r in row["results"]:
            data.append(
                [
                    f"{r.course.code} — {r.course.title}",
                    str(r.course.credit),
                    f"{float(r.marks):.0f}",
                    r.grade,
                    f"{float(r.grade_point):.2f}",
                ]
            )
        data.append(["", "", "", "Semester GPA", f"{row['gpa']:.2f}"])
        table = Table(data, colWidths=[9.5 * cm, 2 * cm, 2 * cm, 2 * cm, 2 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), MAROON),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f6f3f4")]),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f7e3e8")),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e3c9d1")),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("TOPPADDING", (0, 0), (-1, 0), 6),
                ]
            )
        )
        elements.append(Paragraph(f"Semester {row['semester']}", styles["Heading4"]))
        elements.append(table)
        elements.append(Spacer(1, 10))

    elements.append(Spacer(1, 6))
    elements.append(
        Paragraph(
            f"<b>Cumulative GPA (CGPA):</b> {cgpa if cgpa is not None else '—'} / 4.00 "
            f"over {total_credits:g} credits — published results only.",
            styles["Heading3"],
        )
    )
    elements.append(Spacer(1, 18))
    elements.append(
        Paragraph(
            f"Generated on {timezone.localdate():%d %b %Y} · This document was "
            f"generated from the SEC UMS database and shows only published results. "
            f"© Sylhet Engineering College — University Management System. All Rights Reserved.",
            small,
        )
    )

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="transcript_{student.reg_no}.pdf"'
    )
    return response
