from django.urls import path

from . import views

app_name = "academics"

urlpatterns = [
    # Shared
    path("notices/", views.notices_view, name="notices"),
    # Student module
    path("student/", views.student_dashboard, name="student_dashboard"),
    path("student/profile/", views.student_profile, name="student_profile"),
    path("student/attendance/", views.student_attendance, name="student_attendance"),
    path("student/assignments/", views.student_assignments, name="student_assignments"),
    path("student/in-course/", views.student_incourse, name="student_incourse"),
    path("student/results/", views.student_results, name="student_results"),
    path("student/results/pdf/", views.student_results_pdf, name="student_results_pdf"),
    path("student/routine/", views.student_routine, name="student_routine"),
    path("student/fees/", views.student_fees, name="student_fees"),
    # Teacher module
    path("teacher/", views.teacher_dashboard, name="teacher_dashboard"),
    path(
        "teacher/courses/<int:course_id>/students/",
        views.teacher_course_students,
        name="teacher_course_students",
    ),
    path("teacher/attendance/", views.teacher_attendance, name="teacher_attendance"),
    path("teacher/materials/", views.teacher_materials, name="teacher_materials"),
    path(
        "teacher/materials/<int:pk>/delete/",
        views.teacher_material_delete,
        name="teacher_material_delete",
    ),
    path("teacher/assessments/", views.teacher_assessments, name="teacher_assessments"),
    path(
        "teacher/assessments/<int:pk>/delete/",
        views.teacher_assessment_delete,
        name="teacher_assessment_delete",
    ),
    path(
        "teacher/assessments/<int:pk>/marks/",
        views.teacher_assessment_marks,
        name="teacher_assessment_marks",
    ),
    path(
        "teacher/in-course/<int:course_id>/",
        views.teacher_incourse,
        name="teacher_incourse",
    ),
    path("teacher/results/", views.teacher_results_courses, name="teacher_results_courses"),
    path(
        "teacher/results/<int:course_id>/<str:exam_type>/enter/",
        views.teacher_results_entry,
        name="teacher_results_entry",
    ),
    path(
        "teacher/results/<int:course_id>/<str:exam_type>/print/",
        views.teacher_results_print,
        name="teacher_results_print",
    ),
    path("teacher/routine/", views.teacher_routine, name="teacher_routine"),
    path(
        "teacher/routine/<int:pk>/delete/",
        views.teacher_routine_delete,
        name="teacher_routine_delete",
    ),
]
