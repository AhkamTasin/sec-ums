"""Root URL configuration for the University Management System."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django's built-in admin site (kept under /django-admin/ to avoid
    # clashing with the UMS Admin module at /admin-panel/)
    path("django-admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("academics.urls")),
    path("", include("fees.urls")),
    path("", include("library.urls")),
]

if settings.DEBUG:
    # Serve uploaded files (course materials, assignments) in development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
