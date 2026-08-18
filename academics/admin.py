from django.contrib import admin

from .models import (
    Assessment,
    AssessmentMark,
    Attendance,
    Course,
    CourseMaterial,
    Department,
    InCourseMark,
    Notice,
    Result,
    Routine,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "department", "semester", "credit", "teacher")
    list_filter = ("department", "semester")
    search_fields = ("code", "title")


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "exam_type", "marks", "grade", "grade_point")
    list_filter = ("exam_type", "course")


@admin.register(Routine)
class RoutineAdmin(admin.ModelAdmin):
    list_display = ("day", "start_time", "end_time", "course", "semester", "room")


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ("title", "audience", "created_at")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("course", "student", "date", "status")
    list_filter = ("status", "course")


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "uploaded_by", "uploaded_at")


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "course", "max_marks", "due_date")
    list_filter = ("kind", "course")


@admin.register(AssessmentMark)
class AssessmentMarkAdmin(admin.ModelAdmin):
    list_display = ("assessment", "student", "marks")


@admin.register(InCourseMark)
class InCourseMarkAdmin(admin.ModelAdmin):
    list_display = ("course", "student", "term_test", "assignment", "attendance", "total")
    readonly_fields = ("submitted_by", "submitted_at")
