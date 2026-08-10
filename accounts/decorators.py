"""Role-based access control decorators (RBAC core)."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render


def role_required(*roles):
    """Allow only the given roles.

    Super Admins (and Django superusers) bypass every restriction — they can
    access every department and every module.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if user.role in roles or user.is_super_admin:
                return view_func(request, *args, **kwargs)
            return render(request, "403.html", status=403)

        return wrapper

    return decorator


def dept_admin_required(view_func):
    """Department Administrator guard with automatic department scoping.

    Resolves the admin's own department and injects it into the view as the
    ``dept`` argument. Views MUST use this value for every queryset — that is
    what makes it impossible to reach another department's data.

    Department profiles of other roles (or a super admin without a linked
    department) are redirected to the super admin dashboard.
    """

    @wraps(view_func)
    @role_required("DEPT_ADMIN")
    def wrapper(request, *args, **kwargs):
        dept = request.user.managed_department
        if dept is None:
            messages.info(
                request,
                "This area is reserved for Department Administrators. "
                "Super Admins can manage departments from their own panel.",
            )
            return redirect("accounts:admin_dashboard")
        return view_func(request, dept, *args, **kwargs)

    return wrapper
