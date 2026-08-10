from django.urls import path

from . import views

app_name = "fees"

urlpatterns = [
    path("cashier/", views.cashier_dashboard, name="cashier_dashboard"),
    path("cashier/fees/", views.fee_structure_list, name="fee_structures"),
    path("cashier/fees/add/", views.fee_structure_add, name="fee_structure_add"),
    path(
        "cashier/fees/<int:pk>/edit/",
        views.fee_structure_edit,
        name="fee_structure_edit",
    ),
    path("cashier/payments/", views.payment_list, name="payment_list"),
    path("cashier/payments/record/", views.payment_record, name="payment_record"),
    path(
        "cashier/payments/<int:pk>/edit/",
        views.payment_edit,
        name="payment_edit",
    ),
    path("cashier/receipt/<int:pk>/", views.payment_receipt, name="receipt"),
    path("cashier/report/daily/", views.daily_report, name="daily_report"),
    path("cashier/dues/", views.dues_list, name="dues_list"),
    path(
        "cashier/statement/<int:student_id>/",
        views.student_statement,
        name="student_statement",
    ),
]
