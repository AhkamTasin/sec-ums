# SEC UMS — Sylhet Engineering College University Management System

The official-style University Management System of **Sylhet Engineering College (SEC)**, built with **Python (Django), HTML, CSS, Bootstrap 5, JavaScript** and a relational database — CSE 334 Database Management System Sessional project (Sylhet Engineering College, Dept. of CSE).

Fully SEC-branded (logo, maroon/navy identity, favicon, printed documents) with a commercial-ERP design system: landing page, portal login, glass top bar with role-aware search & notifications, **light/dark themes**, SweetAlert2 toasts & confirms, Font Awesome icons, Google fonts (Inter + Plus Jakarta Sans, vendored locally), AOS animations, pagination and professional printable documents.

## Features (per the project proposal)

| Module | Capabilities |
|---|---|
| **Authentication & RBAC** | Secure login/logout, password change, password reset (token flow), session policies, and strict role-based access with decorators, middleware and scoped querysets |
| **Super Admin** | System-wide dashboard & analytics, create/edit departments, create/edit/disable Department Administrators, **create central staff (Librarian / Cashier)** and manage ALL users (enable/disable), publish notices — accesses every department |
| **Department Admin** | ONE administrator per department, strict isolation. Full management of **their own** department: students (add/edit/delete/search/filter/**CSV import & export**), teachers (add/edit/delete), courses & teacher assignment, **semester management** (batch promotion), class routine (create/update/delete), department notices (publish/edit/delete), and **result publication** — review teachers' submitted marks and publish; students never see unpublished results |
| **Student** | Card-based dashboard (GPA, attendance %, today's classes, upcoming exams/deadlines, fee status, recent notices), view/edit limited profile info, attendance summary, assignments with deadlines & marks, in-course marks, published final results with **downloadable PDF transcript**, routine, fees |
| **Teacher** | Assigned courses & students, **attendance management**, **course material uploads**, assessments with per-assessment mark entry (theory: term tests & assignments; lab: quiz, lab work, viva), **auto-calculated in-course marks (out of 40)**, final exam mark entry out of 60 (submits only — publishing stays with the Dept Admin), printable mark sheets, class schedules |
| **Cashier** | Receive payments under the **full-payment policy** — two fees per semester (Admission & Exam, each paid in full at once, amounts auto-filled from the fee structure) with the **exam-fee gate** (unpaid admission must be cleared first), update payment status (Confirm / Pend / Cancel), professional printable receipts (amount-in-words + PAID stamp), searchable payment history, printable daily collection reports, dues list & student bills |
| **Librarian** | Bookstore-style catalogue with cover images, book cards & detail pages, add/edit/delete books (history-safe), search & filters, issue/return books with auto late fines, borrow history, overdue tracking, printable library cards |

### Official grading scheme

| Course type | Course total | Composition |
|---|---|---|
| **Theory course** | **100** = In-course **40** + Final exam **60** | In-course 40 = **Term Test average 20** (TT1 & TT2, each out of 20) + **Assignment 10** + **Attendance 10** (attendance % mapped to marks: ≥90%→10, ≥85%→9, … ≥60%→4). Final exam entered out of 60. |
| **Lab course** | **100** | Teacher-defined components — **quiz + lab work + viva** — whose max marks must sum to **100**; component totals become the course result. |

Grades & grade points follow the UGC scale (80+ → A+/4.00, … , <40 → F). For theory courses the letter grade is computed on the **combined 100** (in-course 40 + final 60) and stamped when the Department Administrator publishes the result; publishing is blocked until in-course marks are submitted for every enrolled student.

**Tech stack:** Django 5 (MVT architecture), Django ORM, MySQL-ready (SQLite by default), Bootstrap 5, Font Awesome, Chart.js.

## Quick start

```bash
cd ums_project
pip install -r requirements.txt     # Django + Pillow (book covers) + ReportLab (PDF results)
python manage.py migrate
python manage.py seed_demo          # loads demo data (idempotent)
python manage.py runserver 0.0.0.0:8000
```

Open http://localhost:8000 and log in with a demo account.

## Demo accounts

| Role | Username | Password |
|---|---|---|
| Super Admin | `admin` | `admin123` |
| Dept Admin — CSE | `D-CSE1` | `deptadmin123` |
| Dept Admin — EEE | `D-EEE1` | `deptadmin123` |
| Dept Admin — CE | `D-CE1` | `deptadmin123` |
| Teacher | `T-1001` *(also T-1002 … T-1004)* | `teacher123` |
| Student | `2024331501` *(also …02 …08)* | `student123` |
| Librarian | `L-1001` | `library123` |
| Cashier | `C-1001` | `cashier123` |

> **Password reset:** click *Forgot password?* on the login page. In this demo
> the reset email is printed to the server console — configure SMTP in
> `ums/settings.py` for production.

Django's built-in admin site is available at `/django-admin/` (superuser: `admin`).

## Switching to MySQL (as per the proposal)

1. Create the database:
   ```sql
   CREATE DATABASE ums_db CHARACTER SET utf8mb4;
   ```
2. Install the driver: `pip install mysqlclient`
3. Run with environment variables:
   ```bash
   USE_MYSQL=1 MYSQL_NAME=ums_db MYSQL_USER=root MYSQL_PASSWORD=secret \
   MYSQL_HOST=127.0.0.1 MYSQL_PORT=3306 \
   python manage.py migrate && python manage.py seed_demo
   ```
All queries go through the Django ORM, so no code changes are required.

## Project layout

```
ums_project/
├── ums/            # project settings & root URLs
├── accounts/       # users, roles, authentication, Admin module, seed_demo
├── academics/      # departments, courses, results, routines, notices
│                   #   (Student + Teacher modules)
├── fees/           # fee structures, payments, receipts, dues (Cashier module)
├── library/        # books, issues/returns, library cards (Librarian module)
├── templates/      # shared + per-module templates
└── static/         # Bootstrap 5, icons, Chart.js (local, no CDN needed)
```

## Roles & access control (RBAC)

| Role | Access |
|---|---|
| **Super Admin** | Everything: all departments, all users, departments CRUD, dept-admin CRUD/disable, analytics |
| **Department Administrator** | Only their **own** department — students, teachers, courses, semesters, routine, notices, result review & publication, dashboard. Other departments are impossible to reach (404) |
| **Teacher** | Own courses: result entry/print (locked once the dept admin publishes), own class routines |
| **Student** | Own **published** results only, routine, fees, notices |
| **Librarian** | Library catalogue (covers, cards, details), issues/returns, borrow history, overdue, library cards |
| **Cashier** | Fee structures, payments & statuses, receipts, daily reports, dues & bills |

Enforcement points:
- `accounts/decorators.py` — `@role_required(...)` (super admin bypass) and `@dept_admin_required` (injects the admin's own department into the view)
- `accounts/middleware.py` — session policy: disabled accounts are force-logged-out; the managed department is attached to every request
- Every dept-admin queryset is filtered by that department; cross-department object access returns **404**, never data.

## Testing

```bash
python smoke_test.py   # full RBAC suite: logins, per-role pages, 403/404 checks,
                       # session policies, dept creation, password reset flow
```
