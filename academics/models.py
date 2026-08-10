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
    code = models.CharField(max_length=15, unique=True)
    title = models.CharField(max_length=150)
    credit = models.DecimalField(max_digits=3, decimal_places=1, default=3.0)
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
    grade = models.CharField(max_length=3, editable=False)
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, editable=False)
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

# In-course mark weights: Mid 30 + Quiz 10 + Assignment 10 + Lab 10 = 60 total
INCOURSE_WEIGHTS = {"mid": 30.0, "quiz": 10.0, "assignment": 10.0, "lab": 10.0}
INCOURSE_TOTAL = sum(INCOURSE_WEIGHTS.values())


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
        ("QUIZ", "Quiz"),
        ("ASSIGNMENT", "Assignment"),
        ("LAB", "Lab Work"),
    ]

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
    mid = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    quiz = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    assignment = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    lab = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    submitted_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("course", "student")
        ordering = ["student__reg_no"]

    def __str__(self):
        return f"{self.course.code} in-course {self.student.reg_no}: {self.total}/60"


def compute_incourse(course, student):
    """Compute in-course components (mid 30, quiz 10, assignment 10, lab 10).

    Mid component comes from the MID result (scaled to 30). Other components
    come from assessments of each kind: (obtained / max) * weight. A component
    with no assessments/marks counts as 0 — teachers should create
    assessments before submitting.
    """
    result = (
        Result.objects.filter(course=course, student=student, exam_type="MID")
        .only("marks")
        .first()
    )
    parts = {"mid": (float(result.marks) / 100) * INCOURSE_WEIGHTS["mid"] if result else 0.0}

    for kind, weight in (
        ("QUIZ", INCOURSE_WEIGHTS["quiz"]),
        ("ASSIGNMENT", INCOURSE_WEIGHTS["assignment"]),
        ("LAB", INCOURSE_WEIGHTS["lab"]),
    ):
        assessments = list(course.assessments.filter(kind=kind).only("id", "max_marks"))
        if not assessments:
            parts[kind.lower()] = 0.0
            continue
        total_max = sum(float(a.max_marks) for a in assessments)
        obtained = (
            AssessmentMark.objects.filter(
                assessment__in=assessments, student=student
            ).aggregate(s=models.Sum("marks"))["s"]
            or 0
        )
        parts[kind.lower()] = (float(obtained) / total_max) * weight if total_max else 0.0

    parts["total"] = sum(parts.values())
    return {k: round(v, 2) for k, v in parts.items()}
