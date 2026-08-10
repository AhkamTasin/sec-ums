"""Forms for the Teacher module (class routines)."""

from django import forms

from accounts.forms import BootstrapFormMixin
from accounts.models import Teacher

from .models import Assessment, Course, CourseMaterial, Routine

TIME_INPUT = forms.TimeInput(attrs={"type": "time"})


class CourseForm(BootstrapFormMixin, forms.ModelForm):
    """Course create/edit for a department (department is set by the view)."""

    class Meta:
        model = Course
        fields = ["code", "title", "credit", "semester", "teacher"]
        help_texts = {"teacher": "Optional — assign later if not decided yet."}

    def __init__(self, *args, locked_department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if locked_department is not None:
            self.fields["teacher"].queryset = Teacher.objects.filter(
                department=locked_department
            ).select_related("user")
        self.fields["teacher"].label_from_instance = (
            lambda t: f"{t.user.get_full_name()} ({t.employee_id})"
        )


class RoutineForm(BootstrapFormMixin, forms.ModelForm):
    """Teachers schedule a class for one of their own courses."""

    class Meta:
        model = Routine
        fields = ["course", "day", "start_time", "end_time", "room"]
        widgets = {"start_time": TIME_INPUT, "end_time": TIME_INPUT}

    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop("teacher")
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = self.teacher.courses.select_related(
            "department"
        )
        self.fields["course"].label_from_instance = (
            lambda c: f"{c.code} — {c.title} ({c.department.code}, Sem {c.semester})"
        )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and end <= start:
            raise forms.ValidationError("End time must be after the start time.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        course = instance.course
        instance.department = course.department
        instance.semester = course.semester
        instance.teacher = self.teacher
        if commit:
            instance.save()
        return instance


class DeptRoutineForm(BootstrapFormMixin, forms.ModelForm):
    """Department Administrators schedule classes for ANY course of their
    department (the slot's department/semester/teacher come from the course)."""

    class Meta:
        model = Routine
        fields = ["course", "day", "start_time", "end_time", "room"]
        widgets = {"start_time": TIME_INPUT, "end_time": TIME_INPUT}

    def __init__(self, *args, **kwargs):
        self.department = kwargs.pop("department")
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = Course.objects.filter(
            department=self.department
        ).select_related("teacher__user")
        self.fields["course"].label_from_instance = (
            lambda c: f"{c.code} — {c.title} (Sem {c.semester})"
        )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and end <= start:
            raise forms.ValidationError("End time must be after the start time.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        course = instance.course
        instance.department = self.department  # never from the request
        instance.semester = course.semester
        instance.teacher = course.teacher  # routine teacher follows the course
        if commit:
            instance.save()
        return instance


class CourseMaterialForm(BootstrapFormMixin, forms.ModelForm):
    """Teachers upload course materials; course locked to their own."""

    class Meta:
        model = CourseMaterial
        fields = ["course", "title", "description", "file"]

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        if teacher is not None:
            self.fields["course"].queryset = teacher.courses.all()
        self.fields["course"].label_from_instance = (
            lambda c: f"{c.code} — {c.title}"
        )


class AssessmentForm(BootstrapFormMixin, forms.ModelForm):
    """Teachers create quizzes / assignments / lab tasks for their courses."""

    class Meta:
        model = Assessment
        fields = ["course", "kind", "title", "description", "max_marks", "due_date", "file"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        if teacher is not None:
            self.fields["course"].queryset = teacher.courses.all()
        self.fields["course"].label_from_instance = (
            lambda c: f"{c.code} — {c.title}"
        )
        self.fields["description"].required = False
        self.fields["due_date"].required = False
        self.fields["file"].required = False
