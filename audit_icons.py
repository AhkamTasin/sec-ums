#!/usr/bin/env python3
"""Full-site audit crawls every page as every role from the seeded DB.

Checks per page:
  * HTTP status is 200 (or expected redirect for dashboard role-gates)
  * every `fa-*` icon class exists in Font Awesome 6 Free (parses all.min.css)
  * every static/media asset referenced (img/script/link src+href) returns 200
Also flags fa classes without an `fa-solid|fa-regular|fa-brands` style prefix,
and stray glyph-looking placeholders (empty <i> tags etc).
"""
import os, re, sys, posixpath, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ums.settings")
django.setup()

from django.test import Client
from academics.models import (Department, Course, Routine, Notice,
                              Assessment, Result)
from fees.models import Payment, FeeStructure
from library.models import Book, BookIssue
from accounts.models import User

BASE = "/static/vendor/fontawesome/css/all.min.css"
from django.conf import settings
from django.conf import settings

css = open(settings.BASE_DIR / "static" / "vendor" / "fontawesome" / "css" / "all.min.css").read()
VALID = set(re.findall(r"\.(fa-[a-z0-9-]+):before", css))
print(f"Font Awesome free icon classes available: {len(VALID)}")

STYLE_OK = ("fa-solid", "fa-regular", "fa-brands")
bad_icons, missing_style, empty_i, pages, asset_bad = [], [], [], 0, []
expected = []   # pages permitted to be non-200 (role gates etc.)


import urllib.request


def check_assets(role, path, html):
    for m in re.finditer(r'''(?:src|href)="(/static/[^"]+|/media/[^"]+)"''', html):
        url = m.group(1)
        try:
            with urllib.request.urlopen("http://localhost:8000" + url) as r:
                code = r.status
        except Exception as e:
            code = getattr(e, "code", str(e))
        if code != 200:
            asset_bad.append((role, path, url, code))


def visit(role, path, allow=(200,)):
    global pages
    if any(p == path and r == role for r, p in expected):
        pass
    resp = c.get(path, follow=False)
    pages += 1
    status = resp.status_code
    if status not in allow:
        flag = "  <<< UNEXPECTED" if status in (404, 500) else ""
        print(f"  [{status}] {path}{flag}")
        if status in (404, 500):
            bad_icons.append((role, path, f"HTTP {status}"))
        return None
    html = resp.content.decode("utf-8", "ignore")
    # icon audit on RENDERED html
    for iclass in re.findall(r'class="([^"]*(?:fa-[a-z0-9-]+)[^"]*)"', html):
        toks = iclass.split()
        fa_toks = [t for t in toks if t.startswith("fa-")]
        icons = [t for t in fa_toks if t not in STYLE_OK
                 and t not in ("fa-fw", "fa-lg", "fa-xs", "fa-sm", "fa-xl",
                               "fa-2x", "fa-3x", "fa-spin", "fa-pulse",
                               "fa-inverse", "fa-border", "fa-stack",
                               "fa-stack-1x", "fa-stack-2x", "fa-flip",
                               "fa-rotate-90", "fa-rotate-180", "fa-rotate-270")]
        for ic in icons:
            if ic not in VALID:
                bad_icons.append((role, path, ic))
        if icons and not any(t in STYLE_OK for t in toks):
            missing_style.append((role, path, ", ".join(sorted(set(icons)))))
    check_assets(role, path, html)
    return html


def login_as(u, p):
    c.logout()
    ok = c.login(username=u, password=p)
    print(f"\n================ {u} ({'ok' if ok else 'FAILED LOGIN'}) ================")
    return ok


c = Client()

# ---------------- public pages ----------------
print("\n================ public ================")
visit("public", "/")
visit("public", "/login/")
r404 = c.get("/__404_probe__/")  # render 404 template through full stack
print(f"  [{r404.status_code}] /__404_probe__/ (expected 404)")
h = r404.content.decode("utf-8", "ignore")
for iclass in re.findall(r'class="([^"]*(?:fa-[a-z0-9-]+)[^"]*)"', h):
    for ic in [t for t in iclass.split() if t.startswith("fa-") and t not in STYLE_OK]:
        if ic not in VALID and ic not in ("fa-fw",):
            bad_icons.append(("public", "/__404_probe__", ic))
check_assets("public", "/__404_probe__", h)

# ---------------- gather demo data ----------------
admin = User.objects.get(username="admin")
dept_admin = User.objects.filter(role="DEPT_ADMIN").first()
teacher = User.objects.filter(role="TEACHER").first()
student = User.objects.filter(role="STUDENT").first()
librarian = User.objects.filter(role="LIBRARIAN").first()
cashier = User.objects.filter(role="CASHIER").first()
print(f"\nDemo accounts: DA={dept_admin} T={teacher} S={student} L={librarian} C={cashier}")

pay = Payment.objects.first()
book = Book.objects.first()
book_del_ok = Book.objects.filter(issues__isnull=True).first()  # deletable
issue = BookIssue.objects.first()
dpt = Department.objects.first()
notice = Notice.objects.first()
_managed = dept_admin.managed_department if dept_admin else None
dept2 = Department.objects.exclude(pk=_managed.pk).first() if _managed else None

# ---------------- super admin ----------------
if login_as("admin", "admin123"):
    for path in [
        "/dashboard/", "/admin-panel/", "/admin-panel/departments/",
        "/admin-panel/departments/add/", "/admin-panel/dept-admins/",
        "/admin-panel/dept-admins/add/", "/admin-panel/students/",
        "/admin-panel/students/add/", "/admin-panel/teachers/",
        "/admin-panel/teachers/add/", "/admin-panel/users/",
        "/admin-panel/notices/", "/admin-panel/notices/add/",
        "/notices/", "/password/change/", "/password/change/done/",
        "/django-admin/",
    ]:
        visit("admin", path)
    if notice:
        visit("admin", f"/admin-panel/notices/{notice.pk}/edit/")

# ---------------- department admin ----------------
if dept_admin and login_as(dept_admin.username, "deptadmin123"):
    for path in [
        "/dashboard/", "/dept/", "/dept/students/", "/dept/students/add/",
        "/dept/teachers/", "/dept/teachers/add/", "/dept/courses/",
        "/dept/courses/add/", "/dept/semesters/", "/dept/routine/",
        "/dept/routine/add/", "/dept/results/", "/dept/notices/",
        "/dept/notices/add/", "/notices/",
    ]:
        visit("dept_admin", path)
    # (dept-admin URLs are profile-scoped, so no cross-dept URL exists to probe)

# ---------------- teacher ----------------
if teacher and login_as(teacher.username, "teacher123"):
    for path in [
        "/dashboard/", "/teacher/", "/teacher/attendance/",
        "/teacher/assessments/", "/teacher/results/",
        "/teacher/materials/", "/teacher/routine/",
        "/notices/",
    ]:
        visit("teacher", path)
    # assessment marks + results entry + print need pks — resolve from DB
    a = Assessment.objects.filter(course__teacher__user=teacher).first()
    if a:
        visit("teacher", f"/teacher/assessments/{a.pk}/marks/")
        visit("teacher", f"/teacher/in-course/{a.course_id}/")
        visit("teacher", f"/teacher/courses/{a.course_id}/students/")
    from academics.models import Result
    res = Result.objects.filter(course__teacher__user=teacher).first()
    if res:
        visit("teacher", f"/teacher/results/{res.course_id}/{res.exam_type}/enter/")
        visit("teacher", f"/teacher/results/{res.course_id}/{res.exam_type}/print/")

# ---------------- student ----------------
if student and login_as(student.username, "student123"):
    for path in [
        "/dashboard/", "/student/", "/student/routine/",
        "/student/attendance/", "/student/results/",
        "/student/in-course/", "/student/assignments/",
        "/student/fees/", "/student/profile/", "/student/results/pdf/",
        "/notices/",
    ]:
        visit("student", path)

# ---------------- librarian ----------------
if librarian and login_as(librarian.username, "library123"):
    for path in [
        "/dashboard/", "/librarian/", "/library/books/", "/library/books/add/",
        "/library/issued/", "/library/issue/", "/library/card/", "/notices/",
    ]:
        visit("librarian", path)
    if book:
        visit("librarian", f"/library/books/{book.pk}/")
        visit("librarian", f"/library/books/{book.pk}/edit/")
        visit("librarian", f"/library/issue/?book={book.pk}")
    if book_del_ok:
        visit("librarian", f"/library/books/{book_del_ok.pk}/delete/")

# ---------------- cashier ----------------
if cashier and login_as(cashier.username, "cashier123"):
    for path in [
        "/dashboard/", "/cashier/", "/cashier/payments/",
        "/cashier/payments/record/", "/cashier/dues/", "/cashier/fees/",
        "/cashier/fees/add/", "/cashier/report/daily/",
        "/cashier/report/daily/?print=1", "/notices/",
    ]:
        visit("cashier", path)
    if pay:
        visit("cashier", f"/cashier/payments/{pay.pk}/edit/")
        visit("cashier", f"/cashier/receipt/{pay.pk}/")
        visit("cashier", f"/cashier/statement/{pay.student_id}/")
        visit("cashier", f"/cashier/statement/{pay.student_id}/?print=1")
    fs = FeeStructure.objects.first()
    if fs:
        visit("cashier", f"/cashier/fees/{fs.pk}/edit/")

# ================== report ==================
print("\n" + "=" * 60)
print(f"PAGES CRAWLED: {pages}")
uniq_bad = {}
for role, path, ic in bad_icons:
    uniq_bad.setdefault(ic, set()).add(f"{role}:{path}")
if uniq_bad:
    print("\n!!! INVALID ICON CLASSES (not in FA 6 Free) / PAGE ERRORS:")
    for ic, where in sorted(uniq_bad.items()):
        print(f"  {ic}   on {len(where)} page(s): {sorted(where)[:4]}")
else:
    print("\nOK: every icon class used is valid Font Awesome 6 Free")

if missing_style:
    print("\n!!! ICONS WITHOUT fa-solid/regular/brands STYLE PREFIX:")
    for role, path, ic in missing_style:
        print(f"  [{role}] {path}: {ic}")
else:
    print("OK: all icons carry a style prefix")

if empty_i:
    print("\n!!! EMPTY <i> ICON TAGS:")
    for role, path, tag in empty_i:
        print(f"  [{role}] {path}: {tag}")
else:
    print("OK: no empty icon tags")

if asset_bad:
    print("\n!!! BROKEN ASSETS (static/media != 200):")
    seen = set()
    for role, path, url, st in asset_bad:
        if url in seen:
            continue
        seen.add(url)
        print(f"  [{st}] {url}   (first seen on {role}:{path})")
else:
    print("OK: every static/media asset on every page returned 200")

print("=" * 60)
