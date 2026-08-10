"""User, role profiles and RBAC models (Authentication module)."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """A single login account with a role that drives access control."""

    class Roles(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        DEPT_ADMIN = "DEPT_ADMIN", "Department Administrator"
        TEACHER = "TEACHER", "Teacher"
        STUDENT = "STUDENT", "Student"
        LIBRARIAN = "LIBRARIAN", "Librarian"
        CASHIER = "CASHIER", "Cashier"

    role = models.CharField(
        max_length=20, choices=Roles.choices, default=Roles.STUDENT
    )
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    @property
    def dashboard_url(self):
        return {
            "SUPER_ADMIN": "accounts:admin_dashboard",
            "DEPT_ADMIN": "accounts:dept_dashboard",
            "STUDENT": "academics:student_dashboard",
            "TEACHER": "academics:teacher_dashboard",
            "LIBRARIAN": "library:librarian_dashboard",
            "CASHIER": "fees:cashier_dashboard",
        }.get(self.role, "accounts:login")

    @property
    def is_super_admin(self):
        return self.role == self.Roles.SUPER_ADMIN or self.is_superuser

    @property
    def managed_department(self):
        """For Department Administrators: the ONE department they manage.

        Returns None for every other role.
        """
        profile = getattr(self, "dept_admin_profile", None)
        return profile.department if profile else None

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


class DepartmentAdmin(models.Model):
    """The single administrator account in charge of one department.

    The OneToOne on ``department`` guarantees a department has at most ONE
    Department Administrator, as required by the RBAC design.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="dept_admin_profile"
    )
    department = models.OneToOneField(
        "academics.Department",
        on_delete=models.PROTECT,
        related_name="administrator",
    )
    appointed_at = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Department Administrator"
        ordering = ["department__code"]

    def __str__(self):
        return f"{self.user.get_full_name()} — Admin of {self.department.code}"


class Student(models.Model):
    """Profile data for a student, linked 1:1 with a login account."""

    GENDER_CHOICES = [("M", "Male"), ("F", "Female"), ("O", "Other")]
    SEMESTER_CHOICES = [(i, f"Semester {i}") for i in range(1, 9)]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="student_profile"
    )
    reg_no = models.CharField("Registration No", max_length=20, unique=True)
    department = models.ForeignKey(
        "academics.Department", on_delete=models.PROTECT, related_name="students"
    )
    semester = models.PositiveSmallIntegerField(choices=SEMESTER_CHOICES, default=1)
    session = models.CharField(max_length=20, help_text="e.g. 2023-24")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default="M")
    date_of_birth = models.DateField(null=True, blank=True)
    guardian_name = models.CharField(max_length=100, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    admission_date = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["reg_no"]

    def __str__(self):
        return f"{self.reg_no} — {self.user.get_full_name()}"


class Teacher(models.Model):
    """Profile data for a teacher, linked 1:1 with a login account."""

    DESIGNATION_CHOICES = [
        ("LECTURER", "Lecturer"),
        ("ASSISTANT_PROFESSOR", "Assistant Professor"),
        ("ASSOCIATE_PROFESSOR", "Associate Professor"),
        ("PROFESSOR", "Professor"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="teacher_profile"
    )
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(
        "academics.Department", on_delete=models.PROTECT, related_name="teachers"
    )
    designation = models.CharField(
        max_length=30, choices=DESIGNATION_CHOICES, default="LECTURER"
    )
    qualification = models.CharField(max_length=120, blank=True)
    joining_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["employee_id"]

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_designation_display()})"
