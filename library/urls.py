from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("librarian/", views.librarian_dashboard, name="librarian_dashboard"),
    path("library/books/", views.book_list, name="book_list"),
    path("library/books/add/", views.book_add, name="book_add"),
    path("library/books/<int:pk>/", views.book_detail, name="book_detail"),
    path("library/books/<int:pk>/edit/", views.book_edit, name="book_edit"),
    path("library/books/<int:pk>/delete/", views.book_delete, name="book_delete"),
    path("library/issue/", views.issue_book, name="issue_book"),
    path("library/issued/", views.issued_list, name="issued_list"),
    path("library/issued/<int:pk>/return/", views.return_book, name="return_book"),
    path("library/card/", views.library_card, name="library_card"),
]
