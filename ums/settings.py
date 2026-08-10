"""
Django settings for the University Management System (UMS) project.

By default the project runs on SQLite so it works out of the box with zero
setup. To use MySQL (as per the project proposal), set the environment
variable USE_MYSQL=1 along with MYSQL_NAME / MYSQL_USER / MYSQL_PASSWORD /
MYSQL_HOST / MYSQL_PORT, e.g.:

    USE_MYSQL=1 MYSQL_NAME=ums_db MYSQL_USER=root MYSQL_PASSWORD=secret \
        python manage.py migrate
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-ums-dev-key-change-me-in-production",
)

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Trust the live-preview proxy hosts for CSRF (HTTPS origins).
CSRF_TRUSTED_ORIGINS = [
    "https://*.e2b.app",
    "https://*.e2b.dev",
    "http://localhost",
    "http://127.0.0.1",
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # UMS apps
    "accounts",
    "academics",
    "fees",
    "library",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # UMS: force-logout disabled accounts + attach the dept admin's department
    "accounts.middleware.UserSessionPolicyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ---------------------------------------------------------------------------
# Session management (authentication module)
# ---------------------------------------------------------------------------
SESSION_COOKIE_AGE = 60 * 60 * 8  # sessions expire after 8 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Demo setup: password-reset emails are printed to the server console instead
# of being sent. Configure a real SMTP backend (e.g. Gmail) for production.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "ums@example.edu"

ROOT_URLCONF = "ums.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.topbar",
            ],
        },
    },
]

WSGI_APPLICATION = "ums.wsgi.application"


# ---------------------------------------------------------------------------
# Database — SQLite by default, MySQL when USE_MYSQL=1 (see README.md)
# ---------------------------------------------------------------------------
if os.environ.get("USE_MYSQL") == "1":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("MYSQL_NAME", "ums_db"),
            "USER": os.environ.get("MYSQL_USER", "root"),
            "PASSWORD": os.environ.get("MYSQL_PASSWORD", ""),
            "HOST": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "PORT": os.environ.get("MYSQL_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Uploaded files (course materials, assignment attachments)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"
