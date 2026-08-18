from django.contrib.auth import views as auth_views
from django.urls import path

from . import views, views_deptadmin

app_name = "accounts"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("dashboard/", views.dashboard_redirect, name="dashboard"),
    # Authentication: login / logout
    path("login/", views.UMSLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Authentication: password change (logged-in users)
    path(
        "password/change/",
        views.UMSPasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "password/change/done/",
        views.UMSPasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    # Authentication: password reset (self-service, token emailed)
    path(
        "password/reset/", views.UMSPasswordResetView.as_view(), name="password_reset"
    ),
    path(
        "password/reset/done/",
        views.UMSPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        views.UMSPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        views.UMSPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    # ================= Super Admin module =================
    path("admin-panel/", views.admin_dashboard, name="admin_dashboard"),
    # Departments
    path("admin-panel/departments/", views.manage_departments, name="manage_departments"),
    path("admin-panel/departments/add/", views.add_department, name="add_department"),
    path(
        "admin-panel/departments/<int:pk>/edit/",
        views.edit_department,
        name="edit_department",
    ),
    # Department Administrators
    path("admin-panel/dept-admins/", views.manage_dept_admins, name="manage_dept_admins"),
    path("admin-panel/dept-admins/add/", views.add_dept_admin, name="add_dept_admin"),
    path(
        "admin-panel/dept-admins/<int:pk>/edit/",
        views.edit_dept_admin,
        name="edit_dept_admin",
    ),
    path(
        "admin-panel/dept-admins/<int:pk>/toggle/",
        views.toggle_dept_admin,
        name="toggle_dept_admin",
    ),
    # All users
    path("admin-panel/users/", views.manage_users, name="manage_users"),
    path("admin-panel/users/add/", views.add_staff, name="add_staff"),
    path("admin-panel/users/<int:pk>/toggle/", views.toggle_user, name="toggle_user"),
    # Students / teachers / notices (existing features)
    path("admin-panel/students/", views.manage_students, name="manage_students"),
    path("admin-panel/students/add/", views.add_student, name="add_student"),
    path("admin-panel/teachers/", views.manage_teachers, name="manage_teachers"),
    path("admin-panel/teachers/add/", views.add_teacher, name="add_teacher"),
    path(
        "admin-panel/teachers/<int:pk>/edit/", views.edit_teacher, name="edit_teacher"
    ),
    path("admin-panel/notices/", views.manage_notices, name="manage_notices"),
    path("admin-panel/notices/add/", views.add_notice, name="add_notice"),
    path("admin-panel/notices/<int:pk>/edit/", views.edit_notice, name="edit_notice"),
    path(
        "admin-panel/notices/<int:pk>/delete/",
        views.delete_notice,
        name="delete_notice",
    ),
    # ================= Department Administrator module =================
    path("dept/", views_deptadmin.dept_dashboard, name="dept_dashboard"),
    # Students: view/search/filter + add/edit/delete + import/export
    path("dept/students/", views_deptadmin.dept_students, name="dept_students"),
    path("dept/students/add/", views_deptadmin.dept_add_student, name="dept_add_student"),
    path(
        "dept/students/import/",
        views_deptadmin.dept_import_students,
        name="dept_import_students",
    ),
    path(
        "dept/students/export/",
        views_deptadmin.dept_export_students,
        name="dept_export_students",
    ),
    path(
        "dept/students/<int:pk>/edit/",
        views_deptadmin.dept_edit_student,
        name="dept_edit_student",
    ),
    path(
        "dept/students/<int:pk>/delete/",
        views_deptadmin.dept_delete_student,
        name="dept_delete_student",
    ),
    # Semester management (batch promotion)
    path("dept/semesters/", views_deptadmin.dept_semesters, name="dept_semesters"),
    path(
        "dept/semesters/promote/",
        views_deptadmin.dept_promote_semester,
        name="dept_promote_semester",
    ),
    # Teachers: view/add/edit/delete
    path("dept/teachers/", views_deptadmin.dept_teachers, name="dept_teachers"),
    path("dept/teachers/add/", views_deptadmin.dept_add_teacher, name="dept_add_teacher"),
    path(
        "dept/teachers/<int:pk>/edit/",
        views_deptadmin.dept_edit_teacher,
        name="dept_edit_teacher",
    ),
    path(
        "dept/teachers/<int:pk>/delete/",
        views_deptadmin.dept_delete_teacher,
        name="dept_delete_teacher",
    ),
    # Courses
    path("dept/courses/", views_deptadmin.dept_courses, name="dept_courses"),
    path("dept/courses/add/", views_deptadmin.dept_add_course, name="dept_add_course"),
    path(
        "dept/courses/<int:pk>/edit/",
        views_deptadmin.dept_edit_course,
        name="dept_edit_course",
    ),
    # Routine: view/create/update/delete
    path("dept/routine/", views_deptadmin.dept_routine, name="dept_routine"),
    path("dept/routine/add/", views_deptadmin.dept_add_routine, name="dept_add_routine"),
    path(
        "dept/routine/<int:pk>/edit/",
        views_deptadmin.dept_edit_routine,
        name="dept_edit_routine",
    ),
    path(
        "dept/routine/<int:pk>/delete/",
        views_deptadmin.dept_delete_routine,
        name="dept_delete_routine",
    ),
    # Notices: publish/edit/delete (department-scoped)
    path("dept/notices/", views_deptadmin.dept_notices, name="dept_notices"),
    path("dept/notices/add/", views_deptadmin.dept_add_notice, name="dept_add_notice"),
    path(
        "dept/notices/<int:pk>/edit/",
        views_deptadmin.dept_edit_notice,
        name="dept_edit_notice",
    ),
    path(
        "dept/notices/<int:pk>/delete/",
        views_deptadmin.dept_delete_notice,
        name="dept_delete_notice",
    ),
    # Results: review + publish workflow
    path("dept/results/", views_deptadmin.dept_results, name="dept_results"),
    path(
        "dept/results/<int:course_id>/<str:exam_type>/",
        views_deptadmin.dept_results_review,
        name="dept_results_review",
    ),
    path(
        "dept/results/<int:course_id>/<str:exam_type>/<str:action>/",
        views_deptadmin.dept_results_publish,
        name="dept_results_publish",
    ),
]
