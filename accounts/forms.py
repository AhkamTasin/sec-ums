"""Forms for authentication and the Super Admin / Department Admin modules."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.db.models import Q

from academics.models import Department, Notice

from .models import DepartmentAdmin, Student, Teacher, User


class BootstrapFormMixin:
    """Give every field its Bootstrap CSS class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(widget, forms.Select):
                css = "form-select"
            elif isinstance(widget, forms.FileInput):
                css = "form-control"
            else:
                css = "form-control"
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {css}".strip()


class StyledAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Username"}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password"})
    )


def _lock_department(form, locked_department):
    """Restrict a form's department field to a single department.

    Used by Department Administrator forms so an admin can never create or
    move records in another department — the field becomes disabled and its
    value always resolves to the admin's own department.
    """
    qs = Department.objects.all()
    if locked_department is not None:
        qs = qs.filter(pk=locked_department.pk)
        form.fields["department"].initial = locked_department
        form.fields["department"].disabled = True
        form.fields["department"].help_text = (
            "You can only manage your own department."
        )
    form.fields["department"].queryset = qs


# ---------------------------------------------------------------------------
# Super Admin — departments
# ---------------------------------------------------------------------------
class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["code", "name"]
        help_texts = {"code": "Short unique code, e.g. CSE, EEE, CE"}


# ---------------------------------------------------------------------------
# Super Admin — department administrators
# ---------------------------------------------------------------------------
class DepartmentAdminCreateForm(BootstrapFormMixin, forms.Form):
    """Create a Department Administrator (only for a free department)."""

    username = forms.CharField(max_length=50)
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)
    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        help_text="Only departments without an administrator are listed.",
    )
    password = forms.CharField(max_length=50, initial="deptadmin123")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.filter(
            administrator__isnull=True
        )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data["username"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            role=User.Roles.DEPT_ADMIN,
        )
        profile = DepartmentAdmin.objects.create(
            user=user, department=data["department"]
        )
        return profile


class DepartmentAdminUpdateForm(BootstrapFormMixin, forms.Form):
    """Edit a Department Administrator / reassign their department."""

    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)
    department = forms.ModelChoiceField(queryset=Department.objects.none())
    is_active = forms.BooleanField(required=False, label="Account active")

    def __init__(self, *args, **kwargs):
        self.profile = kwargs.pop("profile")
        super().__init__(*args, **kwargs)
        # Free departments + this admin's current one stay selectable
        self.fields["department"].queryset = Department.objects.filter(
            Q(administrator__isnull=True) | Q(pk=self.profile.department_id)
        ).distinct()
        user = self.profile.user
        self.initial.update(
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            phone=user.phone,
            department=self.profile.department,
            is_active=user.is_active,
        )

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        user = self.profile.user
        user.first_name = data["first_name"]
        user.last_name = data["last_name"]
        user.email = data.get("email", "")
        user.phone = data.get("phone", "")
        user.is_active = data.get("is_active", True)
        user.save()
        self.profile.department = data["department"]
        self.profile.save()
        return self.profile


# ---------------------------------------------------------------------------
# Super Admin — central staff (Librarian / Cashier)
# ---------------------------------------------------------------------------
class StaffUserCreateForm(BootstrapFormMixin, forms.Form):
    """Create a central staff account — Librarian or Cashier.

    These are system-level roles serving ALL departments (central library,
    central accounts office), so only the Super Admin can create them and
    they have no department profile.
    """

    STAFF_ROLES = [
        (User.Roles.LIBRARIAN, "Librarian"),
        (User.Roles.CASHIER, "Cashier"),
    ]

    username = forms.CharField(
        max_length=50, help_text="Login ID, e.g. L-1002 or C-1002."
    )
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)
    role = forms.ChoiceField(
        choices=STAFF_ROLES,
        help_text="Central staff serve every department — no department is assigned.",
    )
    password = forms.CharField(max_length=50, initial="staff123")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        return User.objects.create_user(
            username=data["username"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            role=data["role"],
        )


# ---------------------------------------------------------------------------
# Student / teacher management (Super Admin: any dept; Dept Admin: own dept)
# ---------------------------------------------------------------------------
class StudentCreateForm(BootstrapFormMixin, forms.Form):
    """Creates a login account *and* the student profile."""

    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)
    reg_no = forms.CharField(label="Registration No", max_length=20)
    department = forms.ModelChoiceField(queryset=None)
    semester = forms.ChoiceField(choices=Student.SEMESTER_CHOICES)
    session = forms.CharField(max_length=20, help_text="e.g. 2024-25")
    gender = forms.ChoiceField(choices=Student.GENDER_CHOICES)
    date_of_birth = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    guardian_name = forms.CharField(max_length=100, required=False)
    guardian_phone = forms.CharField(max_length=20, required=False)
    password = forms.CharField(
        max_length=50,
        initial="student123",
        help_text="Login username will be the registration number.",
    )

    def __init__(self, *args, locked_department=None, **kwargs):
        super().__init__(*args, **kwargs)
        _lock_department(self, locked_department)

    def clean_reg_no(self):
        reg_no = self.cleaned_data["reg_no"].strip()
        if Student.objects.filter(reg_no=reg_no).exists():
            raise forms.ValidationError("A student with this registration number already exists.")
        return reg_no

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data["reg_no"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            role=User.Roles.STUDENT,
        )
        student = Student.objects.create(
            user=user,
            reg_no=data["reg_no"],
            department=data["department"],
            semester=data["semester"],
            session=data["session"],
            gender=data["gender"],
            date_of_birth=data.get("date_of_birth"),
            guardian_name=data.get("guardian_name", ""),
            guardian_phone=data.get("guardian_phone", ""),
        )
        return student


class TeacherCreateForm(BootstrapFormMixin, forms.Form):
    """Creates a login account *and* the teacher profile."""

    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)
    employee_id = forms.CharField(max_length=20)
    department = forms.ModelChoiceField(queryset=None)
    designation = forms.ChoiceField(choices=Teacher.DESIGNATION_CHOICES)
    qualification = forms.CharField(max_length=120, required=False)
    joining_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    password = forms.CharField(
        max_length=50,
        initial="teacher123",
        help_text="Login username will be the employee ID.",
    )

    def __init__(self, *args, locked_department=None, **kwargs):
        super().__init__(*args, **kwargs)
        _lock_department(self, locked_department)

    def clean_employee_id(self):
        employee_id = self.cleaned_data["employee_id"].strip()
        if Teacher.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError("A teacher with this employee ID already exists.")
        return employee_id

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data["employee_id"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            role=User.Roles.TEACHER,
        )
        teacher = Teacher.objects.create(
            user=user,
            employee_id=data["employee_id"],
            department=data["department"],
            designation=data["designation"],
            qualification=data.get("qualification", ""),
            joining_date=data.get("joining_date"),
        )
        return teacher


class TeacherUpdateForm(BootstrapFormMixin, forms.Form):
    """Update an existing teacher's information."""

    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)
    department = forms.ModelChoiceField(queryset=None)
    designation = forms.ChoiceField(choices=Teacher.DESIGNATION_CHOICES)
    qualification = forms.CharField(max_length=120, required=False)
    is_active = forms.BooleanField(required=False, label="Account active")

    def __init__(self, *args, locked_department=None, **kwargs):
        self.teacher = kwargs.pop("teacher")
        super().__init__(*args, **kwargs)
        _lock_department(self, locked_department)
        user = self.teacher.user
        self.initial.update(
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            phone=user.phone,
            department=self.teacher.department,
            designation=self.teacher.designation,
            qualification=self.teacher.qualification,
            is_active=user.is_active,
        )

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        user = self.teacher.user
        user.first_name = data["first_name"]
        user.last_name = data["last_name"]
        user.email = data.get("email", "")
        user.phone = data.get("phone", "")
        user.is_active = data.get("is_active", True)
        user.save()
        self.teacher.department = data["department"]
        self.teacher.designation = data["designation"]
        self.teacher.qualification = data.get("qualification", "")
        self.teacher.save()
        return self.teacher


class NoticeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Notice
        fields = ["title", "body", "audience"]
        widgets = {"body": forms.Textarea(attrs={"rows": 5})}


# ---------------------------------------------------------------------------
# Department Administrator — student edit / CSV import / dept notices
# ---------------------------------------------------------------------------
class StudentUpdateForm(BootstrapFormMixin, forms.Form):
    """Edit an existing student (department locked by the view)."""

    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)
    reg_no = forms.CharField(label="Registration No", max_length=20)
    department = forms.ModelChoiceField(queryset=Department.objects.none())
    semester = forms.ChoiceField(choices=Student.SEMESTER_CHOICES)
    session = forms.CharField(max_length=20)
    gender = forms.ChoiceField(choices=Student.GENDER_CHOICES)
    date_of_birth = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    guardian_name = forms.CharField(max_length=100, required=False)
    guardian_phone = forms.CharField(max_length=20, required=False)
    is_active = forms.BooleanField(required=False, label="Account active")

    def __init__(self, *args, locked_department=None, **kwargs):
        self.student = kwargs.pop("student")
        super().__init__(*args, **kwargs)
        _lock_department(self, locked_department)
        user = self.student.user
        self.initial.update(
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            phone=user.phone,
            reg_no=self.student.reg_no,
            department=self.student.department,
            semester=self.student.semester,
            session=self.student.session,
            gender=self.student.gender,
            date_of_birth=self.student.date_of_birth,
            guardian_name=self.student.guardian_name,
            guardian_phone=self.student.guardian_phone,
            is_active=user.is_active,
        )

    def clean_reg_no(self):
        reg_no = self.cleaned_data["reg_no"].strip()
        clash = (
            Student.objects.filter(reg_no=reg_no).exclude(pk=self.student.pk).exists()
        )
        if clash:
            raise forms.ValidationError("Another student already uses this registration number.")
        return reg_no

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        user = self.student.user
        old_reg_no = self.student.reg_no
        user.username = data["reg_no"]  # username follows reg_no
        user.first_name = data["first_name"]
        user.last_name = data["last_name"]
        user.email = data.get("email", "")
        user.phone = data.get("phone", "")
        user.is_active = data.get("is_active", True)
        user.save()
        self.student.reg_no = data["reg_no"]
        self.student.department = data["department"]
        self.student.semester = data["semester"]
        self.student.session = data["session"]
        self.student.gender = data["gender"]
        self.student.date_of_birth = data.get("date_of_birth")
        self.student.guardian_name = data.get("guardian_name", "")
        self.student.guardian_phone = data.get("guardian_phone", "")
        self.student.save()
        return self.student


class StudentImportForm(BootstrapFormMixin, forms.Form):
    """CSV upload used by Department Administrators to bulk-add students."""

    csv_file = forms.FileField(
        label="CSV file",
        help_text=(
            "Columns: reg_no, first_name, last_name, semester, session "
            "(optional: email, phone, gender, guardian_name, guardian_phone, password)."
        ),
    )

    def clean_csv_file(self):
        f = self.cleaned_data["csv_file"]
        if not f.name.lower().endswith(".csv"):
            raise forms.ValidationError("Please upload a .csv file.")
        if f.size > 2 * 1024 * 1024:
            raise forms.ValidationError("File too large (max 2 MB).")
        return f


class DeptAdminNoticeForm(BootstrapFormMixin, forms.ModelForm):
    """Notices published by a Department Administrator always target their
    own department (assigned in the view); audience is limited to dept members."""

    class Meta:
        model = Notice
        fields = ["title", "body", "audience"]
        widgets = {"body": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["audience"].choices = [
            ("ALL", "Everyone in the department"),
            ("STUDENT", "Students"),
            ("TEACHER", "Teachers"),
        ]


class StudentSelfEditForm(BootstrapFormMixin, forms.Form):
    """Limited self-service editing for students.

    Only contact/guardian fields are editable — academic identity
    (reg no, department, semester) is managed by the Department Administrator.
    """

    phone = forms.CharField(max_length=20, required=False)
    email = forms.EmailField(required=False)
    address = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    guardian_name = forms.CharField(max_length=100, required=False)
    guardian_phone = forms.CharField(max_length=20, required=False)

    def __init__(self, *args, **kwargs):
        self.student = kwargs.pop("student")
        super().__init__(*args, **kwargs)
        user = self.student.user
        self.initial.update(
            phone=user.phone,
            email=user.email,
            address=user.address,
            guardian_name=self.student.guardian_name,
            guardian_phone=self.student.guardian_phone,
        )

    def save(self):
        data = self.cleaned_data
        user = self.student.user
        user.phone = data.get("phone", "")
        user.email = data.get("email", "")
        user.address = data.get("address", "")
        user.save()
        self.student.guardian_name = data.get("guardian_name", "")
        self.student.guardian_phone = data.get("guardian_phone", "")
        self.student.save()
        return self.student
