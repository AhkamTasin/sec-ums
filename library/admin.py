from django.contrib import admin

from .models import Book, BookIssue


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "isbn", "category", "quantity", "available")
    list_filter = ("category",)
    search_fields = ("title", "author", "isbn")


@admin.register(BookIssue)
class BookIssueAdmin(admin.ModelAdmin):
    list_display = ("book", "student", "issue_date", "due_date", "status", "fine")
    list_filter = ("status",)
