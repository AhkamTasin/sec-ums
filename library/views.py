"""Views for the Library module: books, issuing and library cards."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render


def qs_without_page(request):
    """Current GET params (minus `page`) for pagination links."""
    qs = request.GET.copy()
    qs.pop("page", None)
    return qs.urlencode()

from accounts.decorators import role_required
from accounts.models import Student

from .forms import BookForm, IssueForm
from .models import Book, BookIssue


# ---------------------------------------------------------------------------
# Librarian dashboard
# ---------------------------------------------------------------------------
@role_required("LIBRARIAN")
def librarian_dashboard(request):
    from academics.views import visible_notices

    issued_qs = BookIssue.objects.filter(status="ISSUED").select_related(
        "book", "student__user"
    )
    overdue = [i for i in issued_qs if i.is_overdue]
    overdue.sort(key=lambda i: i.due_date)
    context = {
        "total_titles": Book.objects.count(),
        "total_copies": Book.objects.aggregate(t=Sum("quantity"))["t"] or 0,
        "available_copies": Book.objects.aggregate(t=Sum("available"))["t"] or 0,
        "issued_count": issued_qs.count(),
        "overdue_count": len(overdue),
        "overdue_issues": overdue[:8],
        "recent_issues": BookIssue.objects.select_related(
            "book", "student__user"
        )[:6],
        "notices": visible_notices(request.user, limit=5),
    }
    return render(request, "librarian/dashboard.html", context)


# ---------------------------------------------------------------------------
# Book catalogue (card layout, bookstore style)
# ---------------------------------------------------------------------------
@role_required("LIBRARIAN")
def book_list(request):
    books = Book.objects.annotate(times_borrowed=Count("issues")).order_by("title")
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    availability = request.GET.get("availability", "")
    if q:
        books = books.filter(
            Q(title__icontains=q)
            | Q(author__icontains=q)
            | Q(isbn__icontains=q)
            | Q(publisher__icontains=q)
        )
    if category:
        books = books.filter(category=category)
    if availability == "AVAILABLE":
        books = books.filter(available__gt=0)
    elif availability == "OUT":
        books = books.filter(available=0)
    page_obj = Paginator(books, 8).get_page(request.GET.get("page"))
    return render(
        request,
        "librarian/books.html",
        {
            "books": page_obj,
            "page_obj": page_obj,
            "qs_suffix": qs_without_page(request),
            "q": q,
            "category": category,
            "availability": availability,
            "categories": Book.CATEGORY_CHOICES,
        },
    )


@role_required("LIBRARIAN")
def book_detail(request, pk):
    """Book details page — opens when a catalogue card is clicked."""
    book = get_object_or_404(Book, pk=pk)
    issues = (
        BookIssue.objects.filter(book=book)
        .select_related("student__user")
        .order_by("-issue_date", "-id")
    )
    current_issues = [i for i in issues if i.status == "ISSUED"]
    return render(
        request,
        "librarian/book_detail.html",
        {
            "book": book,
            "issues": issues[:15],
            "current_issues": current_issues,
            "times_borrowed": issues.count(),
            "times_returned": issues.filter(status="RETURNED").count(),
        },
    )


@role_required("LIBRARIAN")
def book_add(request):
    form = BookForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        book = form.save(commit=False)
        book.available = book.quantity  # brand-new book: all copies available
        book.save()
        messages.success(request, f"Book '{book.title}' added to the catalogue.")
        return redirect("library:book_detail", pk=book.pk)
    return render(
        request, "librarian/book_form.html", {"form": form, "title": "Add New Book"}
    )


@role_required("LIBRARIAN")
def book_edit(request, pk):
    book = get_object_or_404(Book, pk=pk)
    form = BookForm(request.POST or None, request.FILES or None, instance=book)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Book '{book.title}' updated.")
        return redirect("library:book_detail", pk=book.pk)
    return render(
        request,
        "librarian/book_form.html",
        {"form": form, "book": book, "title": f"Edit Book — {book.title}"},
    )


@role_required("LIBRARIAN")
def book_delete(request, pk):
    """Delete a book — only allowed when it has no circulation history,
    so past borrow records are never lost."""
    book = get_object_or_404(Book, pk=pk)
    if request.method == "POST":
        if book.issues.exists():
            messages.error(
                request,
                f"'{book.title}' cannot be deleted — it has borrow history. "
                "Circulation records must be preserved; you can edit the book or "
                "set its quantity instead.",
            )
            return redirect("library:book_detail", pk=book.pk)
        title = book.title
        if book.cover:
            book.cover.delete(save=False)
        book.delete()
        messages.success(request, f"Book '{title}' removed from the catalogue.")
        return redirect("library:book_list")
    return redirect("library:book_detail", pk=book.pk)


# ---------------------------------------------------------------------------
# Issue / return / borrow history
# ---------------------------------------------------------------------------
@role_required("LIBRARIAN")
def issue_book(request):
    initial = {}
    book_id = request.GET.get("book")
    if book_id and book_id.isdigit():
        initial["book"] = int(book_id)
    form = IssueForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        issue = form.save(commit=False)
        book = issue.book
        if book.available < 1:
            messages.error(request, "That book is no longer available.")
            return redirect("library:issue_book")
        issue.issued_by = request.user
        issue.save()
        book.available -= 1
        book.save()
        messages.success(
            request,
            f"Issued '{book.title}' to {issue.student.user.get_full_name()} "
            f"(due {issue.due_date:%d %b %Y}).",
        )
        return redirect("library:issued_list")
    return render(request, "librarian/issue_form.html", {"form": form})


@role_required("LIBRARIAN")
def issued_list(request):
    """Circulation: currently issued / overdue / returned / full borrow history,
    searchable by book, student name or registration number."""
    status = request.GET.get("status", "ISSUED")
    q = request.GET.get("q", "").strip()
    issues = BookIssue.objects.select_related("book", "student__user")
    if q:
        issues = issues.filter(
            Q(book__title__icontains=q)
            | Q(book__isbn__icontains=q)
            | Q(student__reg_no__icontains=q)
            | Q(student__user__first_name__icontains=q)
            | Q(student__user__last_name__icontains=q)
        )
    if status == "RETURNED":
        issues = issues.filter(status="RETURNED")
    elif status == "OVERDUE":
        issues = [i for i in issues.filter(status="ISSUED") if i.is_overdue]
    elif status == "ALL":
        pass  # full borrow history
    else:
        status = "ISSUED"
        issues = issues.filter(status="ISSUED")
    return render(
        request, "librarian/issued.html", {"issues": issues, "status": status, "q": q}
    )


@role_required("LIBRARIAN")
def return_book(request, pk):
    issue = get_object_or_404(BookIssue, pk=pk, status="ISSUED")
    if request.method == "POST":
        issue.mark_returned()
        if issue.fine > 0:
            messages.warning(
                request, f"'{issue.book.title}' returned late — fine ৳{issue.fine}."
            )
        else:
            messages.success(request, f"'{issue.book.title}' marked as returned.")
    return redirect(request.POST.get("next") or "library:issued_list")


# ---------------------------------------------------------------------------
# Library card generation
# ---------------------------------------------------------------------------
@role_required("LIBRARIAN")
def library_card(request):
    students = Student.objects.select_related("user", "department")
    student = None
    student_id = request.GET.get("student")
    active_issues = []
    borrow_history = []
    total_fines = 0
    if student_id:
        student = get_object_or_404(
            Student.objects.select_related("user", "department"), pk=student_id
        )
        all_issues = BookIssue.objects.filter(student=student).select_related("book")
        active_issues = [i for i in all_issues if i.status == "ISSUED"]
        borrow_history = all_issues[:10]
        total_fines = sum(i.fine for i in all_issues)
    return render(
        request,
        "librarian/library_card.html",
        {
            "students": students,
            "student": student,
            "active_issues": active_issues,
            "borrow_history": borrow_history,
            "total_fines": total_fines,
        },
    )
