"""Departments, Courses, Exam Results, Class Routines and Notices."""

from django.db import models

GRADING_SCALE = [
    (80, "A+", 4.00),
    (75, "A", 3.75),
    (70, "A-", 3.50),
    (65, "B+", 3.25),
    (60, "B", 3.00),
    (55, "B-", 2.75),
    (50, "C+", 2.50),
    (45, "C", 2.25),
    (40, "D", 2.00),
]


def grade_from_marks(marks):
    """Convert numeric marks (0-100) to a letter grade and grade point (UGC scale)."""
    marks = float(marks)
    for threshold, grade, point in GRADING_SCALE:
        if marks >= threshold:
            return grade, point
    return "F", 0.00


class Department(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=10, unique=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Course(models.Model):
    TYPE_CHOICES = [("THEORY", "Theory Course"), ("LAB", "Lab Course")]

    code = models.CharField(max_length=15, unique=True)
    title = models.CharField(max_length=150)
    credit = models.DecimalField(max_digits=3, decimal_places=1, default=3.0)
    course_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="THEORY")
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="courses"
    )
    semester = models.PositiveSmallIntegerField(choices=[(i, f"Semester {i}") for i in range(1, 9)])
    teacher = models.ForeignKey(
        "accounts.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses",
    )

    class Meta:
        ordering = ["department", "semester", "code"]

    @property
    def is_lab(self):
        return self.course_type == "LAB"

    def __str__(self):
        return f"{self.code} — {self.title}"


class Result(models.Model):
    """A student's marks in one exam (midterm/final) of one course."""

    EXAM_CHOICES = [("MID", "Midterm Exam"), ("FINAL", "Final Exam")]

    student = models.ForeignKey(
        "accounts.Student", on_delete=models.CASCADE, related_name="results"
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="results")
    exam_type = models.CharField(max_length=10, choices=EXAM_CHOICES, default="FINAL")
    marks = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=3, editable=False, default="")
    grade_point = models.DecimalField(
        max_digits=3, decimal_places=2, editable=False, default=0
    )
    # Publication workflow: teachers submit marks, only the Department
    # Administrator can publish. Students never see unpublished results.
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_results",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "course", "exam_type")
        ordering = ["course__semester", "course__code"]

    def save(self, *args, **kwargs):
        # Lab-course finals are the full 100 → grade directly. Theory finals
        # are out of 60 — their grade is stamped at publish time using
        # in-course (40) + final (60) combined, never on the raw 60 alone.
        if self.course_id and self.course.is_lab:
            self.grade, self.grade_point = grade_from_marks(self.marks)
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.student.reg_no} | {self.course.code} | "
            f"{self.get_exam_type_display()}: {self.marks} ({self.grade})"
        )


class Routine(models.Model):
    """One weekly class slot in a department's class routine."""

    DAY_CHOICES = [
        ("Sunday", "Sunday"),
        ("Monday", "Monday"),
        ("Tuesday", "Tuesday"),
        ("Wednesday", "Wednesday"),
        ("Thursday", "Thursday"),
        ("Friday", "Friday"),
        ("Saturday", "Saturday"),
    ]

    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="routines"
    )
    semester = models.PositiveSmallIntegerField(choices=[(i, f"Semester {i}") for i in range(1, 9)])
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="routines")
    teacher = models.ForeignKey(
        "accounts.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routines",
    )
    day = models.CharField(max_length=10, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=30)

    class Meta:
        ordering = ["start_time"]

    def __str__(self):
        return f"{self.day} {self.start_time:%H:%M} — {self.course.code} (Room {self.room})"


class Notice(models.Model):
    AUDIENCE_CHOICES = [
        ("ALL", "Everyone"),
        ("STUDENT", "Students"),
        ("TEACHER", "Teachers"),
        ("LIBRARIAN", "Librarians"),
        ("CASHIER", "Cashiers"),
    ]

    title = models.CharField(max_length=200)
    body = models.TextField()
    audience = models.CharField(max_length=15, choices=AUDIENCE_CHOICES, default="ALL")
    # NULL = global notice (Super Admin). Set = department-scoped notice
    # (Department Administrator), visible only to that department.
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notices",
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


# ---------------------------------------------------------------------------
# Teacher coursework: attendance, materials, assessments, in-course marks
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Official marking scheme (theory courses): total 100 = in-course 40 + final 60
#   In-course 40 = Term Test average (20) + Assignment (10) + Attendance (10)
#     - Term Tests: TT1 & TT2, each out of 20 → component = average of the two
#     - Assignments: pooled (Σ obtained / Σ max) scaled to 10
#     - Attendance: percentage mapped to marks by the bracket table below
#   Final exam: entered directly out of 60
# Lab courses: total 100 from teacher-set components (quiz + lab work + viva),
#   entered as assessments whose max marks sum to 100.
# ---------------------------------------------------------------------------
THEORY_WEIGHTS = {"term_test": 20.0, "assignment": 10.0, "attendance": 10.0}
THEORY_INCOURSE_MAX = sum(THEORY_WEIGHTS.values())  # 40
THEORY_FINAL_MAX = 60.0
COURSE_TOTAL_MAX = 100.0

# Attendance % -> marks (out of 10): >=90 → 10, >=85 → 9, ... >=60 → 4, below → 0
ATTENDANCE_MARK_BRACKETS = [(90, 10), (85, 9), (80, 8), (75, 7), (70, 6), (65, 5), (60, 4)]


def attendance_mark(pct):
    """Map an attendance percentage (0-100) to attendance marks (0-10)."""
    for threshold, marks in ATTENDANCE_MARK_BRACKETS:
        if pct >= threshold:
            return float(marks)
    return 0.0


class Attendance(models.Model):
    """One student's attendance status for one course on one date."""

    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("LATE", "Late"),
    ]

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="attendance_records"
    )
    student = models.ForeignKey(
        "accounts.Student", on_delete=models.CASCADE, related_name="attendance_records"
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PRESENT")

    class Meta:
        unique_together = ("course", "student", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.course.code} {self.date} {self.student.reg_no}: {self.status}"


class CourseMaterial(models.Model):
    """A file uploaded by a teacher, visible to that course's students."""

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="materials"
    )
    title = models.CharField(max_length=150)
    description = models.CharField(max_length=300, blank=True)
    file = models.FileField(upload_to="materials/")
    uploaded_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.course.code} — {self.title}"


class Assessment(models.Model):
    """A quiz / assignment / lab task created by a teacher for a course."""

    KIND_CHOICES = [
        ("TT", "Term Test"),
        ("ASSIGNMENT", "Assignment"),
        ("QUIZ", "Quiz"),
        ("LAB", "Lab Work"),
        ("VIVA", "Viva"),
    ]
    # Which kinds count for which course type (in-course components)
    KINDS_FOR_TYPE = {
        "THEORY": ("TT", "ASSIGNMENT"),
        "LAB": ("QUIZ", "LAB", "VIVA"),
    }

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="assessments"
    )
    kind = models.CharField(max_length=15, choices=KIND_CHOICES)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    max_marks = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    due_date = models.DateField(null=True, blank=True)
    file = models.FileField(
        "Attachment (e.g. assignment questions PDF)",
        upload_to="assessments/",
        null=True,
        blank=True,
    )
    date_assigned = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["-due_date", "-date_assigned"]

    def __str__(self):
        return f"{self.course.code} {self.get_kind_display()}: {self.title}"


class AssessmentMark(models.Model):
    """A student's marks in one assessment (quiz/assignment/lab)."""

    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name="marks"
    )
    student = models.ForeignKey(
        "accounts.Student", on_delete=models.CASCADE, related_name="assessment_marks"
    )
    marks = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ("assessment", "student")

    def __str__(self):
        return f"{self.assessment} — {self.student.reg_no}: {self.marks}"


class InCourseMark(models.Model):
    """Calculated in-course marks for one student in one course.

    Teachers calculate and SUBMIT these (snapshot). Only the Department
    Administrator can publish final semester results (see Result.is_published).
    """

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="incourse_marks"
    )
    student = models.ForeignKey(
        "accounts.Student", on_delete=models.CASCADE, related_name="incourse_marks"
    )
    # Theory in-course (out of 40): TT avg (20) + assignment (10) + attendance (10)
    term_test = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    assignment = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    attendance = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    submitted_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("course", "student")
        ordering = ["student__reg_no"]

    def __str__(self):
        return f"{self.course.code} in-course {self.student.reg_no}: {self.total}/40"


def compute_incourse(course, student):
    """Compute THEORY in-course marks (out of 40) for one student.

    Official scheme: TT average (20) + assignment (10) + attendance (10).

    * Term Test component: the average of the two (or N) term tests, each
      normalised by its own max marks → scaled to 20. An unmarked TT counts 0.
    * Assignment component: pooled over assignments —
      (Σ obtained / Σ max) × 10.
    * Attendance component: percentage of attended classes (Late counts as
      attended) mapped through ATTENDANCE_MARK_BRACKETS → 0–10.
    A component with no assessments/records counts as 0 — teachers should
    complete assessments & attendance before submitting.
    """
    parts = {}

    tts = list(course.assessments.filter(kind="TT").only("id", "max_marks"))
    if tts:
        shares = []
        for a in tts:
            mark = (
                AssessmentMark.objects.filter(assessment=a, student=student)
                .only("marks")
                .first()
            )
            shares.append(
                (float(mark.marks) if mark else 0.0) / float(a.max_marks or 1)
            )
        parts["term_test"] = (sum(shares) / len(shares)) * THEORY_WEIGHTS["term_test"]
    else:
        parts["term_test"] = 0.0

    assignments = list(
        course.assessments.filter(kind="ASSIGNMENT").only("id", "max_marks")
    )
    if assignments:
        total_max = sum(float(a.max_marks) for a in assignments)
        obtained = (
            AssessmentMark.objects.filter(
                assessment__in=assignments, student=student
            ).aggregate(s=models.Sum("marks"))["s"]
            or 0
        )
        parts["assignment"] = (
            (float(obtained) / total_max) * THEORY_WEIGHTS["assignment"]
            if total_max
            else 0.0
        )
    else:
        parts["assignment"] = 0.0

    records = Attendance.objects.filter(course=course, student=student)
    total_classes = records.count()
    attended = records.exclude(status="ABSENT").count()  # PRESENT/LATE = attended
    pct = (attended / total_classes * 100) if total_classes else 0.0
    parts["attendance"] = attendance_mark(pct)
    parts["attendance_pct"] = pct

    parts["total"] = parts["term_test"] + parts["assignment"] + parts["attendance"]
    return {k: round(v, 2) for k, v in parts.items()}


def lab_max_total(course):
    """Σ max marks of a LAB course's assessments — teacher must design to 100."""
    return float(
        course.assessments.aggregate(s=models.Sum("max_marks"))["s"] or 0
    )


def compute_lab_total(course, student):
    """LAB course total (out of 100): sum of obtained marks across the
    teacher-set components (quiz / lab work / viva), capped at 100."""
    by_kind = {}
    total_obtained = 0.0
    for kind, label in (("QUIZ", "Quiz"), ("LAB", "Lab Work"), ("VIVA", "Viva")):
        assessments = list(course.assessments.filter(kind=kind).only("id", "max_marks"))
        max_sum = sum(float(a.max_marks) for a in assessments)
        obtained = (
            AssessmentMark.objects.filter(
                assessment__in=assessments, student=student
            ).aggregate(s=models.Sum("marks"))["s"]
            or 0
        ) if assessments else 0
        by_kind[kind.lower()] = {
            "label": label,
            "obtained": float(obtained),
            "max": max_sum,
        }
        total_obtained += float(obtained)
    return {
        "by_kind": by_kind,
        "total": round(min(total_obtained, float(COURSE_TOTAL_MAX)), 2),
        "max_total": lab_max_total(course),
    }


def theory_course_grade(incourse_total, final_marks):
    """Letter grade + point for a THEORY course:
    grade on in-course (40) + final (60) combined out of 100."""
    return grade_from_marks(float(incourse_total) + float(final_marks))
