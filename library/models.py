"""Books and book issues (Library module)."""

from django.db import models
from django.utils import timezone

FINE_PER_DAY = 5  # ৳ per day late


class Book(models.Model):
    CATEGORY_CHOICES = [
        ("PROGRAMMING", "Programming"),
        ("DATABASE", "Database"),
        ("NETWORKING", "Networking"),
        ("MATHEMATICS", "Mathematics"),
        ("ELECTRONICS", "Electronics"),
        ("ENGINEERING", "Engineering"),
        ("FICTION", "Fiction"),
        ("OTHER", "Other"),
    ]

    title = models.CharField(max_length=200)
    author = models.CharField(max_length=150)
    isbn = models.CharField("ISBN", max_length=20, unique=True)
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, default="OTHER")
    publisher = models.CharField(max_length=120, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    shelf = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    cover = models.ImageField(upload_to="covers/", blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    available = models.PositiveIntegerField(default=1)
    added_at = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def save(self, *args, **kwargs):
        if self.available > self.quantity:
            self.available = self.quantity
        super().save(*args, **kwargs)

    @property
    def is_available(self):
        return self.available > 0

    def __str__(self):
        return f"{self.title} — {self.author}"


class BookIssue(models.Model):
    STATUS_CHOICES = [("ISSUED", "Issued"), ("RETURNED", "Returned")]

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="issues")
    student = models.ForeignKey(
        "accounts.Student", on_delete=models.CASCADE, related_name="book_issues"
    )
    issued_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ISSUED")
    fine = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        ordering = ["-issue_date", "-id"]

    @property
    def is_overdue(self):
        return self.status == "ISSUED" and timezone.localdate() > self.due_date

    @property
    def overdue_days(self):
        if not self.is_overdue:
            return 0
        return (timezone.localdate() - self.due_date).days

    def mark_returned(self):
        """Return the book and compute any late fine."""
        self.return_date = timezone.localdate()
        self.status = "RETURNED"
        late_days = (self.return_date - self.due_date).days
        if late_days > 0:
            self.fine = late_days * FINE_PER_DAY
        self.save()
        self.book.available += 1
        self.book.save()

    def __str__(self):
        return f"{self.book.title} → {self.student.reg_no} ({self.status})"
