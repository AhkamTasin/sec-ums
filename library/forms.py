"""Forms for the Library module."""

from datetime import timedelta

from django import forms
from django.utils import timezone

from accounts.forms import BootstrapFormMixin
from accounts.models import Student

from .models import Book, BookIssue


class BookForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            "title",
            "author",
            "isbn",
            "category",
            "publisher",
            "year",
            "shelf",
            "description",
            "cover",
            "quantity",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "cover": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for optional in ("publisher", "year", "shelf", "description", "cover"):
            self.fields[optional].required = False
        self.fields["cover"].help_text = "Optional cover image (JPG/PNG, shown on the catalogue card)."


class IssueForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BookIssue
        fields = ["book", "student", "due_date"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["book"].queryset = Book.objects.filter(available__gt=0)
        self.fields["book"].label_from_instance = (
            lambda b: f"{b.title} — {b.author} ({b.available} available)"
        )
        self.fields["student"].queryset = Student.objects.select_related(
            "user", "department"
        )
        self.fields["student"].label_from_instance = (
            lambda s: f"{s.reg_no} — {s.user.get_full_name()}"
        )
        if not self.is_bound:
            self.initial.setdefault("due_date", timezone.localdate() + timedelta(days=14))

    def clean_due_date(self):
        due = self.cleaned_data["due_date"]
        if due < timezone.localdate():
            raise forms.ValidationError("Due date cannot be in the past.")
        return due
