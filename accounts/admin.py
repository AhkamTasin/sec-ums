from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import DepartmentAdmin, Student, Teacher, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "get_full_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("UMS info", {"fields": ("role", "phone", "address")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("UMS info", {"fields": ("role", "phone", "address")}),
    )


@admin.register(DepartmentAdmin)
class DepartmentAdminAdmin(admin.ModelAdmin):
    list_display = ("user", "get_name", "department", "appointed_at")
    search_fields = ("user__username", "user__first_name", "user__last_name")

    @admin.display(description="Name")
    def get_name(self, obj):
        return obj.user.get_full_name()


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("reg_no", "get_name", "department", "semester", "session")
    search_fields = ("reg_no", "user__first_name", "user__last_name")
    list_filter = ("department", "semester")

    @admin.display(description="Name")
    def get_name(self, obj):
        return obj.user.get_full_name()


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "get_name", "department", "designation")
    search_fields = ("employee_id", "user__first_name", "user__last_name")

    @admin.display(description="Name")
    def get_name(self, obj):
        return obj.user.get_full_name()
