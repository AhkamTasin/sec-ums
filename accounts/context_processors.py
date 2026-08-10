"""Context for the shared layout chrome.

Provides (for every authenticated page):
- ``topbar_search_action`` / ``topbar_search_label`` — where the global
  search box in the top bar should submit, per role (None = box hidden)
- ``top_notices`` — latest notices for the notification bell
"""

from django.urls import reverse

ROLE_SEARCH = {
    "SUPER_ADMIN": ("accounts:manage_students", "students"),
    "DEPT_ADMIN": ("accounts:dept_students", "students"),
    "LIBRARIAN": ("library:book_list", "books"),
    "CASHIER": ("fees:payment_list", "payments"),
}


def topbar(request):
    ctx = {}
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return ctx

    role = getattr(user, "role", "")
    if role in ROLE_SEARCH:
        url_name, label = ROLE_SEARCH[role]
        try:
            ctx["topbar_search_action"] = reverse(url_name)
            ctx["topbar_search_label"] = label
        except Exception:
            pass

    try:
        from academics.views import visible_notices

        ctx["top_notices"] = visible_notices(user, limit=5)
    except Exception:
        ctx["top_notices"] = []
    return ctx
