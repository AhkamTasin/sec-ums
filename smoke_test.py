"""RBAC smoke + functional test (run: python smoke_test.py)."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ums.settings")
import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402

failures = 0


def check(client, url, expect=200):
    global failures
    resp = client.get(url)
    status = resp.status_code
    mark = "OK " if status == expect else "FAIL"
    print(f"  [{mark}] {url} -> {status} (expect {expect})")
    if status != expect:
        failures += 1
    return resp


def expect(cond, label):
    global failures
    print(("  [OK ] " if cond else "  [FAIL] ") + label)
    if not cond:
        failures += 1


def login(username, password):
    c = Client()
    ok = c.login(username=username, password=password)
    print(f"\n== {username} (login {'ok' if ok else 'FAILED'}) ==")
    if not ok:
        expect(ok, f"login as {username}")
    return c


from academics.models import Course, Department  # noqa: E402
from accounts.models import Student, Teacher, User  # noqa: E402

cse = Department.objects.get(code="CSE")
eee = Department.objects.get(code="EEE")
cse_course = Course.objects.filter(department=cse).first()
eee_course = Course.objects.filter(department=eee).first()
cse_teacher = Teacher.objects.get(department=cse, employee_id="T-1001")
eee_teacher = Teacher.objects.get(employee_id="T-1003")

# ======================================================= Super Admin
c = login("admin", "admin123")
for url in [
    "/", "/admin-panel/",
    "/admin-panel/departments/", "/admin-panel/departments/add/",
    f"/admin-panel/departments/{cse.pk}/edit/",
    "/admin-panel/dept-admins/", "/admin-panel/dept-admins/add/",
    "/admin-panel/dept-admins/1/edit/", "/admin-panel/users/",
    "/admin-panel/users/?role=TEACHER&q=rahim",
    "/admin-panel/users/add/",
    "/admin-panel/students/", "/admin-panel/students/add/",
    "/admin-panel/teachers/", f"/admin-panel/teachers/{cse_teacher.pk}/edit/",
    "/admin-panel/notices/", "/admin-panel/notices/add/",
    "/django-admin/", "/password/change/",
]:
    check(c, url)  # "/" is now the public landing page (200 for everyone)
# super admin visiting a dept-only page is redirected gracefully
check(c, "/dept/", 302)

# ---- Super Admin creates central staff (Librarian / Cashier)
resp = c.post("/admin-panel/users/add/", {
    "username": "L-9999", "first_name": "Smoke", "last_name": "Librarian",
    "email": "", "phone": "", "role": "LIBRARIAN", "password": "staff123",
})
staff = User.objects.filter(username="L-9999").first()
expect(staff is not None and staff.role == "LIBRARIAN" and not staff.is_superuser,
       "super admin created a Librarian account")
# duplicate username is rejected
c.post("/admin-panel/users/add/", {
    "username": "l-9999", "first_name": "Dup", "last_name": "User",
    "email": "", "phone": "", "role": "CASHIER", "password": "staff123",
})
expect(User.objects.filter(username__iexact="L-9999").count() == 1,
       "duplicate staff username rejected")
c_staff = login("L-9999", "staff123")
check(c_staff, "/librarian/")
check(c_staff, "/admin-panel/users/add/", 403)  # staff cannot create staff
staff.delete()  # keep demo data pristine

# ======================================================= Department Admin (CSE)
c = login("D-CSE1", "deptadmin123")
for url in [
    "/dept/", "/dept/students/", "/dept/students/add/",
    "/dept/teachers/", "/dept/teachers/add/",
    f"/dept/teachers/{cse_teacher.pk}/edit/",
    "/dept/courses/", "/dept/courses/add/",
    f"/dept/courses/{cse_course.pk}/edit/",
    "/dept/routine/", "/dept/routine/?sem=3",
    "/notices/", "/password/change/", "/dashboard/",
]:
    check(c, url, 302 if url == "/dashboard/" else 200)
# every page of every OTHER module must be forbidden
for url in [
    "/admin-panel/", "/admin-panel/users/", "/admin-panel/departments/",
    "/teacher/", "/student/", "/cashier/", "/librarian/", "/library/books/",
]:
    check(c, url, 403)
# cross-department objects: MUST 404 (never 200/302)
check(c, f"/dept/teachers/{eee_teacher.pk}/edit/", 404)
check(c, f"/dept/courses/{eee_course.pk}/edit/", 404)

# Department admin adds a student — department is hard-locked, tampering ignored
resp = c.post("/dept/students/add/", {
    "first_name": "Test", "last_name": "Locked", "reg_no": "9000000001",
    "department": eee.pk,          # attacker tries EEE...
    "semester": "1", "session": "2025-26", "gender": "M",
    "password": "student123",
})
s = Student.objects.get(reg_no="9000000001")
expect(s.department.code == "CSE", "locked dept: student landed in CSE despite tampered form")

# Department admin edits only own dept courses
resp = c.post(f"/dept/courses/{eee_course.pk}/edit/", {"code": "X"}, follow=False)
expect(resp.status_code == 404, "cannot POST to another department's course")

# ======================================================= Dept Admin: FULL module
print("\n== Dept Admin: complete administration suite ==")
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from academics.models import InCourseMark, Notice, Result, Routine  # noqa: E402
from accounts.models import User as U2  # noqa: E402

cse_student = Student.objects.get(reg_no="2024331501")
pending_course = Course.objects.get(code="CSE 2103")
slot_course = Course.objects.filter(department=cse).last()
eee_student = Student.objects.get(reg_no="2024331505")

# ---- New GET pages
for url in [
    "/dept/students/export/", "/dept/students/import/",
    f"/dept/students/{cse_student.pk}/edit/", "/dept/semesters/",
    "/dept/routine/add/", f"/dept/routine/{Routine.objects.filter(department=cse).first().pk}/edit/",
    "/dept/notices/", "/dept/notices/add/",
    "/dept/results/", f"/dept/results/{pending_course.pk}/FINAL/",
    "/dept/students/?sem=3&q=nafis",
]:
    check(c, url)
html = c.get("/dept/").content.decode()
expect("Pending results" in html and "Published results" in html, "dashboard shows result pipeline stats")

# ---- Import students (2 valid rows, 1 duplicate, 1 invalid)
csv_data = (
    b"reg_no,first_name,last_name,semester,session\n"
    b"9000000010,Test,Import,1,2025-26\n"
    b"9000000012,Second,Valid,2,2025-26\n"
    b"2024331501,Dup,Row,1,2025-26\n"
    b"9000000013,,NoFirst,1,2025-26\n"
)
c.post("/dept/students/import/", {"csv_file": SimpleUploadedFile("students.csv", csv_data, content_type="text/csv")})
expect(Student.objects.filter(reg_no="9000000010", department=cse).exists(), "CSV import created student in OWN dept")
expect(not Student.objects.filter(reg_no="9000000013").exists(), "invalid CSV row skipped")
expect(Student.objects.get(reg_no="2024331501").user.first_name == "Nafis", "duplicate reg not overwritten")

# ---- Export is department-isolated
resp = c.get("/dept/students/export/")
expect(resp["Content-Type"] == "text/csv" and b"2024331501" in resp.content, "export contains own students")
c_eee = login("D-EEE1", "deptadmin123")
resp = c_eee.get("/dept/students/export/")
expect(b"2024331505" in resp.content and b"2024331501" not in resp.content, "EEE export contains ONLY EEE students")

# ---- Edit / Delete student
s12 = Student.objects.get(reg_no="9000000012")
c.post(f"/dept/students/{s12.pk}/edit/", {
    "first_name": "Second", "last_name": "Edited", "phone": "01711111111",
    "reg_no": "9000000012", "department": cse.pk, "semester": "3",
    "session": "2025-26", "gender": "M", "is_active": "on",
})
s12.refresh_from_db()
expect(s12.semester == 3 and s12.user.last_name == "Edited", "student edited")
s12_uid = s12.user_id
c.post(f"/dept/students/{s12.pk}/delete/")
expect(not Student.objects.filter(pk=s12.pk).exists() and not U2.objects.filter(pk=s12_uid).exists(), "student + login deleted")
check(c, f"/dept/students/{eee_student.pk}/edit/", 404)
expect(Student.objects.filter(pk=eee_student.pk).exists(), "cross-dept student untouched")

# ---- Delete teacher (create a temporary one first)
c.post("/dept/teachers/add/", {
    "first_name": "Temp", "last_name": "Teach", "employee_id": "T-9999",
    "department": cse.pk, "designation": "LECTURER", "password": "teacher123",
})
tmp_t = Teacher.objects.get(employee_id="T-9999")
tmp_uid = tmp_t.user_id
c.post(f"/dept/teachers/{tmp_t.pk}/delete/")
expect(not Teacher.objects.filter(pk=tmp_t.pk).exists() and not U2.objects.filter(pk=tmp_uid).exists(), "teacher + login deleted")
check(c, f"/dept/teachers/{eee_teacher.pk}/delete/", 404)
expect(Teacher.objects.filter(pk=eee_teacher.pk).exists(), "cross-dept teacher untouched")

# ---- Course: assign a teacher (T-1002 -> first CSE course)
t2 = Teacher.objects.get(employee_id="T-1002")
c.post(f"/dept/courses/{cse_course.pk}/edit/", {
    "code": cse_course.code, "title": cse_course.title, "credit": cse_course.credit,
    "semester": cse_course.semester, "teacher": t2.pk,
})
cse_course.refresh_from_db()
expect(cse_course.teacher_id == t2.pk, "teacher assigned to course")

# ---- Routine: create / update / delete
c.post("/dept/routine/add/", {
    "course": slot_course.id, "day": "Friday", "start_time": "10:00",
    "end_time": "11:00", "room": "R-9",
})
slot2 = Routine.objects.filter(day="Friday", course_id=slot_course.id, department=cse).first()
expect(
    slot2 is not None
    and slot2.semester == slot_course.semester
    and slot2.teacher_id == slot_course.teacher_id,
    "dept routine created with course-derived fields",
)
c.post(f"/dept/routine/{slot2.pk}/edit/", {
    "course": slot_course.id, "day": "Saturday", "start_time": "12:00",
    "end_time": "13:00", "room": "R-10",
})
slot2.refresh_from_db()
expect(slot2.day == "Saturday" and slot2.room == "R-10", "routine updated")
c.post(f"/dept/routine/{slot2.pk}/delete/")
expect(not Routine.objects.filter(pk=slot2.pk).exists(), "routine deleted")
check(c, f"/dept/routine/{Routine.objects.filter(department=eee).first().pk}/edit/", 404)

# ---- Dept notices: publish / edit / delete + visibility scoping
c.post("/dept/notices/add/", {"title": "CSE Internal Notice", "body": "Only CSE", "audience": "STUDENT"})
n = Notice.objects.get(title="CSE Internal Notice")
expect(n.department_id == cse.id, "dept notice auto-tagged to own department")
c_stud = login("2024331501", "student123")
expect("CSE Internal Notice" in c_stud.get("/notices/").content.decode(), "CSE student sees dept notice")
c_lib = login("L-1001", "library123")
expect("CSE Internal Notice" not in c_lib.get("/notices/").content.decode(), "librarian does NOT see dept notice")
c.post(f"/dept/notices/{n.pk}/edit/", {"title": "CSE Internal v2", "body": "x", "audience": "ALL"})
n.refresh_from_db()
expect(n.title == "CSE Internal v2" and n.department_id == cse.id, "dept notice edited")
global_notice = Notice.objects.filter(department__isnull=True).first()
check(c, f"/dept/notices/{global_notice.pk}/edit/", 404)
c.post(f"/dept/notices/{n.pk}/delete/")
expect(not Notice.objects.filter(pk=n.pk).exists(), "dept notice deleted")

# ---- Results: gate -> teacher in-course -> publish (grades stamped) -> visible -> locked -> unpublish -> editable
cid = pending_course.pk
html = c_stud.get("/student/results/").content.decode()
expect("CSE 2103" not in html, "student CANNOT see pending result")
# publish must be BLOCKED while in-course marks (/40) are missing
c.post(f"/dept/results/{cid}/FINAL/publish/", follow=True)
expect(not Result.objects.filter(course_id=cid, exam_type="FINAL", is_published=True).exists(),
       "publish BLOCKED until in-course marks submitted")
# course teacher (T-1002) submits in-course marks (out of 40) first
c_t = login("T-1002", "teacher123")
c_t.post(f"/teacher/in-course/{cid}/")
expect(InCourseMark.objects.filter(course_id=cid).count() >= 4, "in-course submitted for the whole class")
c.post(f"/dept/results/{cid}/FINAL/publish/")
r = Result.objects.filter(course_id=cid, exam_type="FINAL").first()
expect(r.is_published and r.published_by.username == "D-CSE1", "published with audit trail")
expect(bool(r.grade) and r.grade_point > 0,
       "combined grade (in-course 40 + final 60) stamped at publish time")
html = c_stud.get("/student/results/").content.decode()
expect("CSE 2103" in html, "student sees result AFTER publish")
before = Result.objects.get(student=cse_student, course_id=cid, exam_type="FINAL").marks
new_val = "44" if not str(before).startswith("44") else "45"
c_t.post(f"/teacher/results/{cid}/FINAL/enter/", {f"marks_{cse_student.id}": new_val}, follow=True)
after = Result.objects.get(student=cse_student, course_id=cid, exam_type="FINAL").marks
expect(before == after, "published results LOCKED for teachers")
check(c, f"/dept/results/{eee_course.pk}/FINAL/", 404)
c.post(f"/dept/results/{cid}/FINAL/unpublish/")
expect(not Result.objects.filter(course_id=cid, exam_type="FINAL", is_published=True).exists(), "unpublish hides results again")
c_t.post(f"/teacher/results/{cid}/FINAL/enter/", {f"marks_{cse_student.id}": new_val})
expect(str(Result.objects.get(student=cse_student, course_id=cid, exam_type="FINAL").marks).startswith(new_val), "teacher edits allowed after unpublish")

# ---- Lab course results: components (quiz+lab+viva = 100) -> totals -> publish
lab_course = Course.objects.get(code="CSE 2104")  # lab totals submitted, awaiting publish
check(c, f"/dept/results/{lab_course.pk}/FINAL/")  # review page lists lab totals
c.post(f"/dept/results/{lab_course.pk}/FINAL/publish/")
lr = Result.objects.filter(course_id=lab_course.pk, exam_type="FINAL").first()
expect(lr.is_published and bool(lr.grade), "lab totals (/100) published with letter grade")

# ---- Semester management: batch promote
s10 = Student.objects.get(reg_no="9000000010")
c.post("/dept/semesters/promote/", {"from_semester": "1"})
s10.refresh_from_db()
expect(s10.semester == 2, "batch promotion 1 -> 2 works")

# ======================================================= other roles keep working

# ======================================================= other roles keep working
for user, pw, urls in [
    ("2024331501", "student123",
     ["/student/", "/student/results/", "/student/routine/", "/student/fees/", "/notices/"]),
    ("C-1001", "cashier123",
     ["/cashier/", "/cashier/fees/", "/cashier/payments/", "/cashier/dues/", "/notices/"]),
    ("L-1001", "library123",
     ["/librarian/", "/library/books/", "/library/issued/", "/library/card/", "/notices/"]),
]:
    c = login(user, pw)
    for url in urls:
        check(c, url)
    check(c, "/admin-panel/", 403)
    check(c, "/dept/", 403)

# ======================================================= Librarian module suite
print("\n== Librarian module suite ==")
import io  # noqa: E402
from datetime import timedelta  # noqa: E402

from django.utils import timezone  # noqa: E402
from library.models import Book, BookIssue  # noqa: E402

c = login("L-1001", "library123")
s7 = Student.objects.get(reg_no="2024331507")

for url in [
    "/library/books/",
    "/library/books/?q=python&category=PROGRAMMING&availability=AVAILABLE",
    "/library/books/?availability=OUT",
    "/library/issue/", "/library/card/",
    "/library/issued/?status=ALL", "/library/issued/?status=OVERDUE",
    "/library/issued/?status=RETURNED&q=nafis",
]:
    check(c, url)

# bookstore card layout: catalogue shows cards with cover + ISBN labels
html = c.get("/library/books/").content.decode()
expect("book-card" in html and "ISBN" in html and "media/covers/" in html,
       "catalogue renders bookstore cards with cover images")

# book details page (click-through from a card)
db_book = Book.objects.get(isbn="9780078022159")
html = c.get(f"/library/books/{db_book.pk}/").content.decode()
expect("Times borrowed" in html and "Borrow History" in html and db_book.isbn in html,
       "book detail page shows info + borrow history")

# add a book WITH a cover image upload
from PIL import Image  # noqa: E402
buf = io.BytesIO()
Image.new("RGB", (60, 80), (99, 102, 241)).save(buf, "PNG")
buf.seek(0)
c.post("/library/books/add/", {
    "title": "Test Driven Django", "author": "A Writer", "isbn": "9990001112223",
    "category": "PROGRAMMING", "publisher": "", "year": "2024", "shelf": "T-01",
    "quantity": "2", "description": "demo book",
    "cover": SimpleUploadedFile("cover.png", buf.read(), content_type="image/png"),
})
tb = Book.objects.filter(isbn="9990001112223").last()
expect(tb is not None and bool(tb.cover), "book added with cover image upload")

# edit book details
c.post(f"/library/books/{tb.pk}/edit/", {
    "title": "Test Driven Django 2e", "author": "A Writer", "isbn": "9990001112223",
    "category": "PROGRAMMING", "publisher": "", "year": "2025", "shelf": "T-01",
    "quantity": "3", "description": "",
})
tb.refresh_from_db()
expect(tb.title == "Test Driven Django 2e" and tb.quantity == 3, "book edited")

# delete: works without history, blocked with history
c.post(f"/library/books/{tb.pk}/delete/")
expect(not Book.objects.filter(isbn="9990001112223").exists(),
       "book without history deleted")
c.post(f"/library/books/{db_book.pk}/delete/")
expect(Book.objects.filter(pk=db_book.pk).exists(),
       "book WITH borrow history cannot be deleted")

# issue a book -> stock decremented; receive return -> stock restored
avail_before = db_book.available
c.post("/library/issue/", {
    "book": str(db_book.pk), "student": str(s7.pk),
    "due_date": (timezone.localdate() + timedelta(days=10)).isoformat(),
})
iss = BookIssue.objects.filter(book=db_book, student=s7, status="ISSUED").last()
db_book.refresh_from_db()
expect(iss is not None and db_book.available == avail_before - 1,
       "book issued, availability decremented")
c.post(f"/library/issued/{iss.pk}/return/")
db_book.refresh_from_db()
iss.refresh_from_db()
expect(db_book.available == avail_before and iss.status == "RETURNED",
       "return received, availability restored")

# non-librarian roles are blocked
c_s = login("2024331501", "student123")
check(c_s, "/library/books/add/", 403)
check(c_s, "/library/issue/", 403)

# ======================================================= Cashier module suite
print("\n== Cashier module suite ==")
from fees.models import Payment  # noqa: E402
from fees.services import amount_in_words, student_account  # noqa: E402

c = login("C-1001", "cashier123")
s3 = Student.objects.get(reg_no="2024331503")   # CSE sem-3: admission unpaid
s4 = Student.objects.get(reg_no="2024331504")   # CSE sem-3: fully paid
s5 = Student.objects.get(reg_no="2024331505")   # EEE sem-2: admission+exam due

for url in [
    "/cashier/", "/cashier/payments/",
    "/cashier/payments/?status=PENDING&method=CASH",
    "/cashier/report/daily/",
    f"/cashier/report/daily/?date={timezone.localdate().isoformat()}&print=1",
]:
    check(c, url)

# amount-suggest endpoint: exact full due of a fee head + exam gate
import json as _json  # noqa: E402
resp = c.get(f"/cashier/payments/suggest/?student={s5.pk}&fee_type=ADMISSION")
d = _json.loads(resp.content)
expect(float(d["amount"]) == 12000 and "full payment" in d["hint"].lower(),
       f"suggest returns admission due 12000 (got {d['amount']})")
resp = c.get(f"/cashier/payments/suggest/?student={s5.pk}&fee_type=EXAM")
d = _json.loads(resp.content)
expect(d["amount"] == "" and "locked" in d["hint"].lower(),
       "suggest reports exam gate when admission unpaid")
resp = c.get(f"/cashier/payments/suggest/?student={s4.pk}&fee_type=ADMISSION")
d = _json.loads(resp.content)
expect("already fully paid" in d["hint"] and d["amount"] == "",
       "suggest reports fully-paid heads without pre-filling")

# dashboard shows the four required headline stats
html = c.get("/cashier/").content.decode()
for label in ["Today's collection", "Pending fees", "Paid students", "Due students"]:
    expect(label in html, f"cashier dashboard shows '{label}'")

# POLICY: exam fee locked while admission fee unpaid (s3 owes sem-3 admission)
exam_before = Payment.objects.filter(student=s3, fee_type="EXAM").count()
resp = c.post("/cashier/payments/record/", {
    "student": str(s3.pk), "fee_type": "EXAM", "amount": "2500",
    "method": "CASH", "status": "CONFIRMED",
    "payment_date": timezone.localdate().isoformat(), "note": "gate test",
})
expect(Payment.objects.filter(student=s3, fee_type="EXAM").count() == exam_before
       and "unpaid admission fee" in resp.content.decode(),
       "exam fee BLOCKED until admission fee cleared")

# POLICY: no installments — partial amount of a head rejected
adm_before = Payment.objects.filter(student=s5, fee_type="ADMISSION").count()
resp = c.post("/cashier/payments/record/", {
    "student": str(s5.pk), "fee_type": "ADMISSION", "amount": "5000",
    "method": "CASH", "status": "CONFIRMED",
    "payment_date": timezone.localdate().isoformat(), "note": "partial test",
})
expect(Payment.objects.filter(student=s5, fee_type="ADMISSION").count() == adm_before
       and "installments" in resp.content.decode(),
       "partial payment rejected — full amount enforced")

# receive FULL payment -> receipt generated, due reduced, exam gate opens
_, paid_before, _ = student_account(s5)
c.post("/cashier/payments/record/", {
    "student": str(s5.pk), "fee_type": "ADMISSION", "amount": "12000",
    "method": "CASH", "status": "CONFIRMED",
    "payment_date": timezone.localdate().isoformat(), "note": "smoke test",
})
p = Payment.objects.filter(student=s5, fee_type="ADMISSION").order_by("-id").first()
expect(p is not None and p.receipt_no.startswith("RC-"),
       "payment received, receipt number generated")
_, paid_after, _ = student_account(s5)
expect(paid_after - paid_before == 12000, "confirmed full payment reduces student due")
resp = c.get(f"/cashier/payments/suggest/?student={s5.pk}&fee_type=EXAM")
d = _json.loads(resp.content)
expect(float(d["amount"]) == 2400, "exam fee UNLOCKED after admission cleared (2400 due)")

# professional receipt renders (amount in words + status stamp)
html = c.get(f"/cashier/receipt/{p.pk}/").content.decode()
expect("In words" in html and "PAID" in html and "Authorized Signature" in html,
       "printable receipt renders with words + stamp")
expect(amount_in_words(52000) == "Taka Fifty-Two Thousand Only",
       f"amount_in_words correct ({amount_in_words(52000)})")

# edit form: amount & fee type are LOCKED; only status/method/date/note change
c.post(f"/cashier/payments/{p.pk}/edit/", {
    "fee_type": "EXAM", "amount": "999", "method": "CASH", "status": "PENDING",
    "payment_date": timezone.localdate().isoformat(), "note": "smoke test",
})
p.refresh_from_db()
expect(p.amount == 12000 and p.fee_type == "ADMISSION",
       "amount & fee type immutable on edit")
_, paid_pending, _ = student_account(s5)
expect(p.status == "PENDING" and paid_pending == paid_before,
       "pending payment no longer counts as paid")

# daily report lists today's receipt
html = c.get("/cashier/report/daily/").content.decode()
expect(p.receipt_no in html, "daily report includes today's receipt")

# cancel/void the payment
c.post(f"/cashier/payments/{p.pk}/edit/", {
    "method": "CASH", "status": "CANCELLED",
    "payment_date": timezone.localdate().isoformat(), "note": "smoke test",
})
p.refresh_from_db()
expect(p.status == "CANCELLED", "payment cancelled via update form")

# RBAC: cashier and student blocked from each other's modules
check(c, "/librarian/", 403)
check(c_s, "/cashier/", 403)
check(c_s, f"/cashier/payments/{p.pk}/edit/", 403)

# ======================================================= Teacher coursework module
print("\n== Teacher coursework suite ==")
from academics.models import (  # noqa: E402
    Assessment,
    AssessmentMark,
    Attendance,
    CourseMaterial,
    InCourseMark,
)

c = login("T-1001", "teacher123")
ds = Course.objects.get(code="CSE 2101")       # theory course, owned by T-1001
lab = Course.objects.get(code="CSE 2102")      # lab course, owned by T-1001
tt = Assessment.objects.filter(course=ds, kind="TT").first()
s1 = Student.objects.get(reg_no="2024331501")

for url in [
    "/teacher/", "/teacher/results/", "/teacher/routine/", "/notices/",
    f"/teacher/courses/{ds.pk}/students/",
    "/teacher/attendance/", f"/teacher/attendance/?course={ds.pk}",
    "/teacher/materials/", "/teacher/assessments/", "/teacher/assessments/?kind=TT",
    f"/teacher/assessments/{tt.pk}/marks/",
    f"/teacher/in-course/{ds.pk}/",     # theory in-course page
    f"/teacher/in-course/{lab.pk}/",    # lab components page
]:
    check(c, url)
check(c, "/admin-panel/", 403)

# take attendance for a date
from datetime import date  # noqa: E402
target = "2026-08-06"
c.post("/teacher/attendance/", {
    "course": str(ds.pk), "date": target,
    "save_attendance": "1",
    f"att_{s1.id}": "PRESENT",
})
a = Attendance.objects.filter(course=ds, student=s1, date=date(2026, 8, 6))
expect(a.exists() and a.first().status == "PRESENT", "attendance saved")

# upload course material
c.post("/teacher/materials/", {
    "course": str(ds.pk), "title": "Test Slides", "description": "x",
    "file": SimpleUploadedFile("slides.txt", b"lecture notes demo", content_type="text/plain"),
})
expect(CourseMaterial.objects.filter(title="Test Slides", course=ds).exists(), "material uploaded")

# quizzes do NOT belong to theory courses (kind guard per course type)
c.post("/teacher/assessments/", {
    "course": str(ds.pk), "kind": "QUIZ", "title": "Quiz Bad", "description": "",
    "max_marks": "10", "due_date": "2026-08-20",
})
expect(not Assessment.objects.filter(title="Quiz Bad", course=ds).exists(),
       "QUIZ kind rejected for a THEORY course")
# lab components must sum to 100 — a 4th component pushing past 100 is refused
c.post("/teacher/assessments/", {
    "course": str(lab.pk), "kind": "QUIZ", "title": "Quiz Extra", "description": "",
    "max_marks": "10", "due_date": "2026-08-20",
})
expect(not Assessment.objects.filter(title="Quiz Extra", course=lab).exists(),
       "lab component exceeding the 100-mark budget rejected")
# a term test on a theory course works + marks entry
c.post("/teacher/assessments/", {
    "course": str(ds.pk), "kind": "TT", "title": "Term Test 3 (smoke)", "description": "",
    "max_marks": "20", "due_date": "2026-08-20",
})
qa = Assessment.objects.filter(title="Term Test 3 (smoke)", course=ds).last()
expect(qa is not None, "TT kind accepted for a THEORY course")
c.post(f"/teacher/assessments/{qa.pk}/marks/", {f"marks_{s1.id}": "18"})
expect(AssessmentMark.objects.get(assessment=qa, student=s1).marks == 18, "assessment mark saved")
# over-max rejected
c.post(f"/teacher/assessments/{qa.pk}/marks/", {f"marks_{s1.id}": "25"})
expect(AssessmentMark.objects.get(assessment=qa, student=s1).marks == 18, "over-max mark rejected")

# calculate + submit in-course marks
c.post(f"/teacher/in-course/{ds.pk}/")
im = InCourseMark.objects.get(course=ds, student=s1)
expect(im.total > 0 and im.submitted_by.username == "T-1001", "in-course marks submitted with audit")

# cross-teacher access blocked (T-1002 does not own CSE 2101)
c2 = login("T-1002", "teacher123")
check(c2, f"/teacher/courses/{ds.pk}/students/", 404)
check(c2, f"/teacher/in-course/{ds.pk}/", 404)
resp = c2.post(f"/teacher/in-course/{ds.pk}/")
expect(resp.status_code == 404, "cannot submit in-course for another teacher's course")
c2.post(f"/teacher/assessments/{tt.pk}/delete/")
expect(Assessment.objects.filter(pk=tt.pk).exists(), "cannot delete another teacher's assessment")

# teacher CANNOT publish final results (dept admin endpoint is forbidden)
check(c, f"/dept/results/{ds.pk}/FINAL/publish/", 403)

# ======================================================= Student module suite
print("\n== Student module suite ==")
c = login("2024331501", "student123")
for url in [
    "/student/profile/", "/student/attendance/", "/student/assignments/",
    "/student/in-course/", "/student/results/pdf/",
]:
    check(c, url)
resp = c.get("/student/results/pdf/")
expect(resp["Content-Type"] == "application/pdf" and resp.content.startswith(b"%PDF"), "result PDF generated")
html = c.get("/student/").content.decode()
expect("Attendance" in html and "Upcoming Exams" in html, "dashboard shows attendance + upcoming")
# in-course marks: CSE 2101 submitted -> visible
html = c.get("/student/in-course/").content.decode()
expect("CSE 2101" in html, "submitted in-course marks visible to student")
# assessments page shows term tests + assignments + lab components
html = c.get("/student/assignments/").content.decode()
expect("Term Test 1" in html and "Assignment 1" in html, "student sees assessments with deadlines")
expect("Final Viva" in html, "student sees lab-course components too")
# limited profile edit: phone/address editable, identity untouched
c.post("/student/profile/", {
    "phone": "01900-999999", "email": "nafis@example.com", "address": "Sylhet",
    "guardian_name": "Abdul Karim", "guardian_phone": "01733-300300",
})
s1.refresh_from_db()
expect(s1.user.phone == "01900-999999" and s1.semester == 3 and s1.reg_no == "2024331501",
       "limited profile edit keeps academic identity")
# student cannot touch teacher pages
check(c, "/teacher/", 403)
check(c, f"/teacher/in-course/{ds.pk}/", 403)

# ======================================================= session policy: disabled account
c_admin = login("admin", "admin123")
from accounts.models import DepartmentAdmin  # noqa: E402
da = DepartmentAdmin.objects.get(user__username="D-CE1")
c_client = login("D-CE1", "deptadmin123")
c_admin.post(f"/admin-panel/dept-admins/{da.pk}/toggle/")
expect(c_client.get("/dept/").status_code == 302, "disabled dept admin session killed by middleware")
c_client = Client()
expect(not c_client.login(username="D-CE1", password="deptadmin123"), "disabled account cannot log in")
c_admin.post(f"/admin-panel/dept-admins/{da.pk}/toggle/")  # re-enable for clean state

# toggle_user guards
admin_pk = 1
me_pk = None
from accounts.models import User as U  # noqa: E402
me_pk = U.objects.get(username="admin").pk
super_pk = me_pk
c_admin.post(f"/admin-panel/users/{me_pk}/toggle/")
expect(U.objects.get(pk=me_pk).is_active, "super admin cannot disable self")

# department creation + one-admin rule
resp = c_admin.post("/admin-panel/departments/add/", {"code": "BBA", "name": "Dept of Business Admin"})
expect(Department.objects.filter(code="BBA").exists(), "super admin created department BBA")
c_admin.post("/admin-panel/dept-admins/add/", {
    "username": "D-BBA1", "first_name": "Bba", "last_name": "Boss",
    "department": Department.objects.get(code="BBA").pk, "password": "deptadmin123",
})
expect(U.objects.filter(username="D-BBA1", role="DEPT_ADMIN").exists(), "dept admin created for BBA")
# BBA no longer offered in create form (already has an admin)
html = c_admin.get("/admin-panel/dept-admins/add/").content.decode()
expect("D-BBA" not in html or "BBA" not in html.split("department")[1][:600], "BBA not re-offered")

# ======================================================= password reset flow
c = Client()
resp = c.post("/password/reset/", {"email": "admin@ums.edu"})
expect(resp.status_code == 302, "password reset request accepted")
from django.contrib.auth.tokens import default_token_generator  # noqa: E402
from django.utils.encoding import force_bytes  # noqa: E402
from django.utils.http import urlsafe_base64_encode  # noqa: E402
student_user = U.objects.get(username="2024331501")
uid = urlsafe_base64_encode(force_bytes(student_user.pk))
token = default_token_generator.make_token(student_user)
confirm_url = f"/password/reset/{uid}/{token}/"
r = c.get(confirm_url, follow=False)
expect(r.status_code == 302 and "set-password" in r.headers["Location"], "reset link redirects to set-password")
set_pw_url = r.headers["Location"]
resp = c.post(set_pw_url, {"new_password1": "newpass456", "new_password2": "newpass456"}, follow=False)
expect(resp.status_code == 302, "reset password accepted")
expect(Client().login(username="2024331501", password="newpass456"), "login with reset password")
c_restore = login("admin", "admin123")
student_user.set_password("student123")  # restore demo state
student_user.save()

print(f"\n{'ALL PASSED' if failures == 0 else str(failures) + ' FAILURES'}")
sys.exit(0 if failures == 0 else 1)
