"""Session management + request-level RBAC middleware."""

from django.contrib import auth, messages
from django.shortcuts import redirect


class UserSessionPolicyMiddleware:
    """Applies two session policies on every request:

    1. **Disabled-account policy** — if a user's account is disabled
       (``is_active=False``) while they hold a live session, the session is
       destroyed immediately and they are sent back to the login page.
    2. **Department scoping** — for Department Administrators, their managed
       department is attached to ``request.managed_department`` so views can
       scope every query to their own department (``None`` for other roles).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated:
            if not user.is_active:
                auth.logout(request)
                messages.error(
                    request,
                    "Your account has been disabled. Please contact the Super Admin.",
                )
                return redirect("accounts:login")
            request.managed_department = user.managed_department
        else:
            request.managed_department = None
        return self.get_response(request)
