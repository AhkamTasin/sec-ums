"""Seed the database with demo data: departments, users, courses, results,
routines, fees, payments, books, issues and notices.

Marking scheme demoed here (official):
  * Theory courses: total 100 = in-course 40 (TT avg 20 + assignment 10 +
    attendance 10) + final exam 60. Grades are stamped at publish time on
    the combined /100.
  * Lab courses: total 100 from teacher-set components (quiz + lab work +
    viva) whose max marks sum to 100; totals become the course result.

Usage:  python manage.py seed_demo
"""

from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from academics.models import (
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
    compute_incourse,
    compute_lab_total,
    theory_course_grade,
)
from accounts.models import DepartmentAdmin, Student, Teacher, User
from fees.models import FeeStructure, Payment
from library.covers import attach_generated_cover
from library.models import Book, BookIssue

STUDENT_PASSWORD = "student123"
TEACHER_PASSWORD = "teacher123"
DEPT_ADMIN_PASSWORD = "deptadmin123"


def final_for(reg, course_index):
    """Deterministic demo final-exam marks between 32 and 58 (out of 60)."""
    return 32 + (int(reg) + course_index * 7) % 27


def amark(reg, seed, max_marks):
    """Deterministic assessment mark: roughly 60%–95% of ``max_marks``."""
    return round(float(max_marks) * (0.60 + ((int(reg) + seed * 7) % 8) * 0.05), 2)


def hist_incourse(reg, course_index):
    """Synthetic but plausible in-course component split (out of 40) for
    already-completed semesters (no live assessments/attendance exist)."""
    base = int(reg)
    tt = 13.0 + (base + course_index * 3) % 7       # 13..19 of 20
    asn = 7.0 + (base + course_index * 2) % 3       # 7..9 of 10
    att = 7.0 + (base + course_index) % 4           # 7..10 of 10
    return {
        "term_test": round(tt, 2),
        "assignment": round(asn, 2),
        "attendance": round(att, 2),
        "total": round(tt + asn + att, 2),
    }


class Command(BaseCommand):
    help = "Seed the database with demo data for the UMS."

    def handle(self, *args, **options):
        if Department.objects.exists():
            self.stdout.write(self.style.WARNING("Data already exists — skipping seed."))
            return

        # ------------------------------------------------------------------
        # Departments
        # ------------------------------------------------------------------
        cse = Department.objects.create(name="Computer Science & Engineering", code="CSE")
        eee = Department.objects.create(name="Electrical & Electronic Engineering", code="EEE")
        ce = Department.objects.create(name="Civil Engineering", code="CE")

        # ------------------------------------------------------------------
        # Staff login accounts
        # ------------------------------------------------------------------
        admin = User.objects.create_superuser(
            username="admin", password="admin123",
            first_name="System", last_name="Admin", role=User.Roles.SUPER_ADMIN,
            email="admin@ums.edu",
        )

        # One Department Administrator per department (RBAC core rule)
        def make_dept_admin(username, first, last, dept):
            user = User.objects.create_user(
                username=username, password=DEPT_ADMIN_PASSWORD,
                first_name=first, last_name=last, role=User.Roles.DEPT_ADMIN,
                phone="01711-500500",
            )
            return DepartmentAdmin.objects.create(user=user, department=dept)

        da_cse = make_dept_admin("D-CSE1", "Aminul", "Haque", cse)
        make_dept_admin("D-EEE1", "Nasrin", "Sultana", eee)
        make_dept_admin("D-CE1", "Faisal", "Karim", ce)
        cashier_user = User.objects.create_user(
            username="C-1001", password="cashier123",
            first_name="Kamrul", last_name="Hassan", role=User.Roles.CASHIER,
            phone="01711-000003",
        )
        librarian_user = User.objects.create_user(
            username="L-1001", password="library123",
            first_name="Rokeya", last_name="Begum", role=User.Roles.LIBRARIAN,
            phone="01711-000004",
        )

        # ------------------------------------------------------------------
        # Teachers
        # ------------------------------------------------------------------
        def make_teacher(emp_id, first, last, dept, designation, qualification):
            user = User.objects.create_user(
                username=emp_id, password=TEACHER_PASSWORD,
                first_name=first, last_name=last, role=User.Roles.TEACHER,
                phone="01711-100100",
            )
            return Teacher.objects.create(
                user=user, employee_id=emp_id, department=dept,
                designation=designation, qualification=qualification,
                joining_date=date(2020, 1, 5),
            )

        t1 = make_teacher("T-1001", "Dr. Rahim", "Uddin", cse, "PROFESSOR", "PhD in Computer Science")
        t2 = make_teacher("T-1002", "Mahmudul", "Hasan", cse, "ASSISTANT_PROFESSOR", "M.Sc. in CSE")
        t3 = make_teacher("T-1003", "Dr. Sharmin", "Akter", eee, "ASSOCIATE_PROFESSOR", "PhD in EEE")
        t4 = make_teacher("T-1004", "Tanvir", "Hossain", ce, "LECTURER", "M.Sc. in Civil Eng.")

        # ------------------------------------------------------------------
        # Courses (theory courses + lab courses)
        # ------------------------------------------------------------------
        def course(code, title, credit, dept, semester, teacher, course_type="THEORY"):
            return Course.objects.create(
                code=code, title=title, credit=credit, course_type=course_type,
                department=dept, semester=semester, teacher=teacher,
            )

        cse_sem1 = [
            course("CSE 1101", "Structured Programming", 4.0, cse, 1, t2),
            course("CSE 1102", "Discrete Mathematics", 3.0, cse, 1, t1),
            course("EEE 1101", "Basic Electrical Engineering", 3.0, cse, 1, t3),
        ]
        cse_sem1_lab = course("CSE 1104", "Structured Programming Lab", 1.5, cse, 1, t2, "LAB")
        cse_sem2 = [
            course("CSE 1201", "Object Oriented Programming", 4.0, cse, 2, t2),
            course("CSE 1202", "Digital Logic Design", 3.0, cse, 2, t3),
            course("MAT 1201", "Calculus & Linear Algebra", 3.0, cse, 2, t1),
        ]
        cse_sem3 = [
            course("CSE 2101", "Data Structures", 4.0, cse, 3, t1),
            course("CSE 2103", "Database Management Systems", 3.0, cse, 3, t2),
            course("CSE 2105", "Computer Architecture", 3.0, cse, 3, t3),
        ]
        ds_lab = course("CSE 2102", "Data Structures Lab", 1.5, cse, 3, t1, "LAB")
        db_lab = course("CSE 2104", "Database Management Systems Lab", 1.5, cse, 3, t2, "LAB")
        course("EEE 1201", "Circuit Analysis", 4.0, eee, 2, t3)
        course("EEE 1203", "Electronics I", 3.0, eee, 2, t3)
        course("CE 1101", "Engineering Drawing", 3.0, ce, 1, t4)
        course("CE 1103", "Surveying", 3.0, ce, 1, t4)

        # ------------------------------------------------------------------
        # Students
        # ------------------------------------------------------------------
        def make_student(reg, first, last, gender, dept, semester, guardian):
            user = User.objects.create_user(
                username=reg, password=STUDENT_PASSWORD,
                first_name=first, last_name=last, role=User.Roles.STUDENT,
                phone="01722-200200",
            )
            return Student.objects.create(
                user=user, reg_no=reg, department=dept, semester=semester,
                session="2024-25", gender=gender, date_of_birth=date(2004, 5, 15),
                guardian_name=guardian, guardian_phone="01733-300300",
            )

        s1 = make_student("2024331501", "Nafis", "Ahmed", "M", cse, 3, "Abdul Karim")
        s2 = make_student("2024331502", "Ayesha", "Siddika", "F", cse, 3, "Md. Siddik")
        s3 = make_student("2024331503", "Tanvir", "Rahman", "M", cse, 3, "Mizanur Rahman")
        s4 = make_student("2024331504", "Farhana", "Akter", "F", cse, 3, "Akter Hossain")
        s5 = make_student("2024331505", "Mehdi", "Hasan", "M", eee, 2, "Kamal Hasan")
        s6 = make_student("2024331506", "Sultana", "Jahan", "F", eee, 2, "Jahan Alam")
        s7 = make_student("2024331507", "Rakibul", "Islam", "M", ce, 1, "Sirajul Islam")
        s8 = make_student("2024331508", "Mim", "Chowdhury", "F", ce, 1, "Chowdhury Saheb")

        cse_students = [s1, s2, s3, s4]
        now = timezone.now()
        today = date.today()

        # ------------------------------------------------------------------
        # Assessments & marks (current semester coursework)
        # ------------------------------------------------------------------
        ds_course = cse_sem3[0]   # CSE 2101 theory (t1) — fully seeded
        db_course = cse_sem3[1]   # CSE 2103 theory (t2) — partially seeded (demo work)
        ca_course = cse_sem3[2]   # CSE 2105 theory (t3) — barely started

        def assess(course, kind, title, max_marks, due=None, description=""):
            return Assessment.objects.create(
                course=course, kind=kind, title=title, max_marks=max_marks,
                due_date=due, description=description,
            )

        # --- CSE 2101 (theory): TT1 + TT2 (each /20) + assignment (/10), all marked
        tt1 = assess(ds_course, "TT", "Term Test 1 — Arrays, Linked Lists & Stacks", 20,
                     today - timedelta(days=21))
        tt2 = assess(ds_course, "TT", "Term Test 2 — Trees & Graphs", 20,
                     today - timedelta(days=7))
        as1 = assess(ds_course, "ASSIGNMENT", "Assignment 1 — Implement a Binary Tree", 10,
                     today - timedelta(days=10), "Submit source code and output screenshots")

        # --- CSE 2103 (theory): TT1 marked, TT2 created but UNMARKED (teacher
        #     can demo entering marks), assignment marked.
        b_tt1 = assess(db_course, "TT", "Term Test 1 — ER Modelling & SQL", 20,
                       today - timedelta(days=14))
        b_tt2 = assess(db_course, "TT", "Term Test 2 — Normalization & Transactions", 20,
                       today - timedelta(days=2))
        b_as1 = assess(db_course, "ASSIGNMENT", "Assignment 1 — Design a Library Schema", 10,
                       today - timedelta(days=5), "ER diagram + normalized schema")

        # --- CSE 2105 (theory): only the first term test, upcoming & unmarked
        assess(ca_course, "TT", "Term Test 1 — Number Systems & ALU Design", 20,
               today + timedelta(days=9))

        # --- CSE 2102 (lab): quiz 10+10 + lab work 50 + viva 30 = 100, marked
        l_q1 = assess(ds_lab, "QUIZ", "Quiz 1 — Array & Linked List Operations", 10,
                      today - timedelta(days=12))
        l_q2 = assess(ds_lab, "QUIZ", "Quiz 2 — Stacks, Queues & Trees", 10,
                      today - timedelta(days=4))
        l_lab = assess(ds_lab, "LAB", "Lab Performance, Reports & Final Lab Test", 50,
                       today - timedelta(days=6))
        l_viva = assess(ds_lab, "VIVA", "Final Viva-Voce", 30,
                        today - timedelta(days=2))

        # --- CSE 2104 (lab): quiz 20 + lab work 50 + viva 30 = 100, marked
        m_q1 = assess(db_lab, "QUIZ", "Quiz 1 — SQL Queries & Joins", 20,
                      today - timedelta(days=8))
        m_lab = assess(db_lab, "LAB", "Lab Work — Schema Design & Query Practice", 50,
                       today - timedelta(days=3))
        m_viva = assess(db_lab, "VIVA", "Final Viva-Voce", 30,
                        today - timedelta(days=1))

        def mark(assessment, students, seed):
            for s in students:
                AssessmentMark.objects.create(
                    assessment=assessment, student=s,
                    marks=amark(s.reg_no, seed, assessment.max_marks),
                )

        # Theory in-course inputs (CSE 2101 fully marked; CSE 2103 TT2 pending)
        for i, a in enumerate((tt1, tt2, as1)):
            mark(a, cse_students, seed=i + 1)
        mark(b_tt1, cse_students, seed=5)
        mark(b_as1, cse_students, seed=6)
        # Lab components, fully marked
        for i, a in enumerate((l_q1, l_q2, l_lab, l_viva)):
            mark(a, cse_students, seed=i + 10)
        for i, a in enumerate((m_q1, m_lab, m_viva)):
            mark(a, cse_students, seed=i + 20)

        # ------------------------------------------------------------------
        # Attendance: past 2 weeks for the current CSE sem-3 courses
        # ------------------------------------------------------------------
        for i, c in enumerate([ds_course, db_course, ds_lab]):
            for day_offset in range(12, 0, -3):
                d = today - timedelta(days=day_offset)
                for s in cse_students:
                    status = "PRESENT"
                    if (int(s.reg_no[-2:]) + day_offset + i) % 11 == 0:
                        status = "ABSENT"
                    elif (int(s.reg_no[-2:]) + day_offset + i) % 7 == 0:
                        status = "LATE"
                    Attendance.objects.create(course=c, student=s, date=d, status=status)

        # ------------------------------------------------------------------
        # Course material for CSE 2101
        # ------------------------------------------------------------------
        from django.core.files.base import ContentFile
        mat = CourseMaterial.objects.create(
            course=ds_course, title="Week 5 — Trees (Lecture Slides)",
            description="Binary trees, traversals, AVL rotations",
            uploaded_by=t1.user,
        )
        mat.file.save(
            "cse2101-week5-trees.txt",
            ContentFile(
                b"CSE 2101 Data Structures - Week 5 Lecture Notes\n"
                b"Topics: Binary Trees, BST operations, AVL rotations.\n"
                b"(Demo material file generated by seed_demo)\n"
            ),
        )

        # ------------------------------------------------------------------
        # Results & in-course marks
        #   * Completed semesters 1-2: in-course submitted + FINAL published
        #     with combined grades stamped -> visible on transcripts.
        #   * CSE 2101: full pipeline done (in-course + final + published).
        #   * CSE 2103/2105: finals submitted, awaiting in-course + publish.
        #   * Lab courses: totals (/100) become the FINAL result directly;
        #     CSE 2102 published, CSE 2104 awaiting publish.
        # ------------------------------------------------------------------
        def publish_theory(student, c, index, published_by, when, submitted_by):
            ic = hist_incourse(student.reg_no, index)
            InCourseMark.objects.create(
                course=c, student=student, **ic,
                submitted_by=submitted_by, submitted_at=when,
            )
            marks = final_for(student.reg_no[-4:], index)
            grade, point = theory_course_grade(ic["total"], marks)
            Result.objects.create(
                student=student, course=c, exam_type="FINAL", marks=marks,
                grade=grade, grade_point=point,
                is_published=True, published_at=when, published_by=published_by,
            )

        for student in cse_students:
            # History: semesters 1-2 theory courses, completed & published
            for i, c in enumerate(cse_sem1 + cse_sem2):
                publish_theory(student, c, i, published_by=da_cse.user,
                               when=now, submitted_by=c.teacher.user)
            # History lab CSE 1104: total /100 published (auto-graded on save)
            Result.objects.create(
                student=student, course=cse_sem1_lab, exam_type="FINAL",
                marks=45 + (int(student.reg_no[-4:]) + 3) % 50,
                is_published=True, published_at=now, published_by=da_cse.user,
            )

            # CSE 2101: in-course computed from the real seeded assessments +
            # attendance, then finals published with combined grades stamped.
            calc = compute_incourse(ds_course, student)
            InCourseMark.objects.create(
                course=ds_course, student=student,
                term_test=calc["term_test"], assignment=calc["assignment"],
                attendance=calc["attendance"], total=calc["total"],
                submitted_by=t1.user, submitted_at=now,
            )
            marks = final_for(student.reg_no[-4:], 6)
            grade, point = theory_course_grade(calc["total"], marks)
            Result.objects.create(
                student=student, course=ds_course, exam_type="FINAL", marks=marks,
                grade=grade, grade_point=point,
                is_published=True, published_at=now, published_by=da_cse.user,
            )

            # CSE 2103 + CSE 2105: finals submitted, NOT published and no
            # in-course yet -> demonstrates the publish gate (in-course first).
            for j, c in enumerate((db_course, ca_course)):
                Result.objects.create(
                    student=student, course=c, exam_type="FINAL",
                    marks=final_for(student.reg_no[-4:], 7 + j),
                )

            # Lab courses: component totals (/100) submitted as the result.
            # CSE 2102 published (auto-graded), CSE 2104 awaiting publish.
            lt = compute_lab_total(ds_lab, student)
            Result.objects.create(
                student=student, course=ds_lab, exam_type="FINAL",
                marks=lt["total"], is_published=True,
                published_at=now, published_by=da_cse.user,
            )
            mt = compute_lab_total(db_lab, student)
            Result.objects.create(
                student=student, course=db_lab, exam_type="FINAL", marks=mt["total"],
            )

        # ------------------------------------------------------------------
        # Class routines
        # ------------------------------------------------------------------
        def slot(dept, semester, c, teacher, day, start, end, room):
            Routine.objects.create(
                department=dept, semester=semester, course=c, teacher=teacher,
                day=day, start_time=start, end_time=end, room=room,
            )

        slot(cse, 3, cse_sem3[0], t1, "Sunday", time(9, 0), time(10, 30), "301")
        slot(cse, 3, cse_sem3[1], t2, "Sunday", time(11, 0), time(12, 30), "302")
        slot(cse, 3, cse_sem3[2], t3, "Monday", time(9, 0), time(10, 30), "303")
        slot(cse, 3, cse_sem3[0], t1, "Tuesday", time(9, 0), time(10, 30), "301")
        slot(cse, 3, cse_sem3[1], t2, "Wednesday", time(11, 0), time(12, 30), "302")
        slot(cse, 3, cse_sem3[2], t3, "Thursday", time(14, 0), time(15, 30), "303")
        slot(cse, 3, ds_lab, t1, "Monday", time(11, 0), time(13, 0), "Lab-1")
        slot(cse, 3, db_lab, t2, "Thursday", time(9, 0), time(11, 0), "Lab-2")
        slot(eee, 2, Course.objects.get(code="EEE 1201"), t3, "Sunday", time(9, 0), time(10, 30), "E-201")
        slot(eee, 2, Course.objects.get(code="EEE 1203"), t3, "Tuesday", time(11, 0), time(12, 30), "E-202")
        slot(ce, 1, Course.objects.get(code="CE 1101"), t4, "Monday", time(10, 30), time(12, 0), "C-101")
        slot(ce, 1, Course.objects.get(code="CE 1103"), t4, "Wednesday", time(9, 0), time(10, 30), "C-102")

        # ------------------------------------------------------------------
        # Fee structures — public university policy: per semester only two
        # fees exist, Admission Fee (semester start) and Exam Fee (before
        # the final exam).  Each is paid IN FULL at once — no installments.
        # ------------------------------------------------------------------
        def fees(dept, semester, **kw):
            for fee_type, amount in kw.items():
                FeeStructure.objects.create(
                    department=dept, semester=semester, fee_type=fee_type, amount=amount,
                )

        fees(cse, 1, ADMISSION=15000, EXAM=2500)   # sem-1 admission includes enrolment
        fees(cse, 2, ADMISSION=12000, EXAM=2500)
        fees(cse, 3, ADMISSION=12000, EXAM=2500)
        fees(eee, 1, ADMISSION=14500, EXAM=2400)
        fees(eee, 2, ADMISSION=12000, EXAM=2400)
        fees(ce, 1, ADMISSION=14000, EXAM=2200)

        # ------------------------------------------------------------------
        # Payments (spread over recent months so charts look alive)
        # ------------------------------------------------------------------
        def pay(student, fee_type, amount, y, m, d):
            Payment.objects.create(
                student=student, fee_type=fee_type, amount=amount,
                method="CASH", payment_date=date(y, m, d), received_by=cashier_user,
            )

        # Full-head payments only (no installments):
        #   s1 Nafis   — sem 1-3 admission paid; sem-3 EXAM due (gate-ready)
        #   s2 Ayesha  — everything paid (sem-3 EXAM paid TODAY, below)
        #   s3 Tanvir  — sem 1-2 done; sem-3 BOTH unpaid -> the exam-gate demo:
        #                must clear admission first, then exam (both together)
        #   s4 Farhana — everything paid
        #   s5 Mehdi   — sem-1 done; sem-2 BOTH unpaid
        #   s6 Sultana — sem-1 done, sem-2 admission paid; EXAM slip PENDING
        #   s7 Rakibul — sem-1 admission unpaid (dues demo)
        #   s8 Mim     — sem-1 admission + exam paid (card; 1 duplicate voided)
        pay(s1, "ADMISSION", 15000, 2026, 2, 10)
        pay(s1, "EXAM", 2500, 2026, 5, 12)
        pay(s1, "ADMISSION", 12000, 2026, 3, 15)
        pay(s1, "EXAM", 2500, 2026, 6, 9)
        pay(s1, "ADMISSION", 12000, 2026, 7, 25)          # sem-3 admission paid
        pay(s2, "ADMISSION", 15000, 2026, 2, 11)
        pay(s2, "EXAM", 2500, 2026, 5, 13)
        pay(s2, "ADMISSION", 12000, 2026, 3, 18)
        pay(s2, "EXAM", 2500, 2026, 6, 10)
        pay(s2, "ADMISSION", 12000, 2026, 8, 1)           # sem-3 admission
        pay(s3, "ADMISSION", 15000, 2026, 2, 12)
        pay(s3, "EXAM", 2500, 2026, 5, 15)
        pay(s3, "ADMISSION", 12000, 2026, 4, 2)
        pay(s3, "EXAM", 2500, 2026, 6, 26)                # sem-2 done, sem-3 due
        pay(s4, "ADMISSION", 15000, 2026, 2, 15)
        pay(s4, "EXAM", 2500, 2026, 5, 28)
        pay(s4, "ADMISSION", 12000, 2026, 3, 30)
        pay(s4, "EXAM", 2500, 2026, 7, 2)
        pay(s4, "ADMISSION", 12000, 2026, 8, 3)           # sem-3 admission
        pay(s4, "EXAM", 2500, 2026, 8, 6)                 # sem-3 exam — fully paid
        pay(s5, "ADMISSION", 14500, 2026, 3, 5)
        pay(s5, "EXAM", 2400, 2026, 6, 14)                # sem-1 done, sem-2 due
        pay(s6, "ADMISSION", 14500, 2026, 3, 8)
        pay(s6, "EXAM", 2400, 2026, 7, 5)                 # sem-1 done
        pay(s6, "ADMISSION", 12000, 2026, 7, 26)          # sem-2 admission
        pay(s8, "ADMISSION", 14000, 2026, 4, 3)           # CE sem-1 admission
        Payment.objects.create(                             # CE sem-1 exam via card
            student=s8, fee_type="EXAM", amount=2200, method="CARD",
            payment_date=date(2026, 8, 5), received_by=cashier_user,
        )

        # ------------------------------------------------------------------
        # Library books (covers are drawn locally with Pillow — no downloads)
        # ------------------------------------------------------------------
        def book(title, author, isbn, category, publisher, year, shelf, qty, description=""):
            b = Book.objects.create(
                title=title, author=author, isbn=isbn, category=category,
                publisher=publisher, year=year, shelf=shelf, quantity=qty,
                available=qty, description=description,
            )
            attach_generated_cover(b)

        book("Database System Concepts", "Abraham Silberschatz", "9780078022159", "DATABASE", "McGraw-Hill", 2019, "DB-01", 4,
             "The classic database textbook — covers relational models, SQL, normalization, transactions and recovery with clear examples.")
        book("Introduction to Algorithms", "Thomas H. Cormen", "9780262033848", "PROGRAMMING", "MIT Press", 2009, "AL-02", 3,
             "The standard algorithms reference (CLRS): sorting, graphs, dynamic programming, NP-completeness and more.")
        book("Python Crash Course", "Eric Matthes", "9781593279288", "PROGRAMMING", "No Starch Press", 2019, "PR-01", 5,
             "A hands-on, project-based introduction to programming in Python — from basics to web apps and data visualisation.")
        book("Clean Code", "Robert C. Martin", "9780132350884", "PROGRAMMING", "Prentice Hall", 2008, "PR-02", 2,
             "A handbook of agile software craftsmanship: naming, functions, formatting and refactoring for readable code.")
        book("Computer Networks", "Andrew S. Tanenbaum", "9780132126953", "NETWORKING", "Pearson", 2010, "NW-01", 3,
             "Layered network architectures, TCP/IP, routing and congestion — the standard networks text used worldwide.")
        book("Operating System Concepts", "Abraham Silberschatz", "9781118063330", "ENGINEERING", "Wiley", 2012, "OS-01", 3,
             "Processes, threads, memory management, file systems and security — the 'dinosaur book' of operating systems.")
        book("Advanced Engineering Mathematics", "Erwin Kreyszig", "9780470458365", "MATHEMATICS", "Wiley", 2011, "MT-01", 4,
             "Comprehensive engineering mathematics: ODEs, linear algebra, vector calculus, Fourier analysis and PDEs.")
        book("Digital Design", "M. Morris Mano", "9780132774208", "ELECTRONICS", "Pearson", 2012, "EL-01", 2,
             "Logic gates, combinational and sequential circuits, registers, counters and HDL-based digital design.")
        book("Data Structures and Algorithms in C++", "Michael T. Goodrich", "9780470383278", "PROGRAMMING", "Wiley", 2011, "DS-01", 3,
             "Arrays, linked lists, trees, heaps, hash tables and graphs with analysis — taught through modern C++.")
        book("Discrete Mathematics and Its Applications", "Kenneth Rosen", "9780073383095", "MATHEMATICS", "McGraw-Hill", 2011, "MT-02", 3,
             "Logic, sets, combinatorics, graph theory and number theory — the foundation maths course for CSE.")
        book("Fundamentals of Electric Circuits", "Charles Alexander", "9780073380575", "ELECTRONICS", "McGraw-Hill", 2012, "EL-02", 2,
             "Circuit laws, theorems, AC analysis and frequency response with hundreds of solved practice problems.")
        book("Engineering Mechanics: Statics", "R.C. Hibbeler", "9780133918922", "ENGINEERING", "Pearson", 2015, "CE-01", 2,
             "Force systems, equilibrium, structures, friction and centroids — the essential statics text for civil engineers.")

        # ------------------------------------------------------------------
        # Book issues
        # ------------------------------------------------------------------
        db_book = Book.objects.get(isbn="9780078022159")
        clean_code = Book.objects.get(isbn="9780132350884")
        algorithms = Book.objects.get(isbn="9780262033848")
        python_cc = Book.objects.get(isbn="9781593279288")

        # 1. Overdue issue (Nafis)
        i = BookIssue.objects.create(
            book=db_book, student=s1, issued_by=librarian_user,
            issue_date=today - timedelta(days=20), due_date=today - timedelta(days=6),
        )
        db_book.available -= 1
        db_book.save()

        # 2. Active issue (Ayesha)
        BookIssue.objects.create(
            book=algorithms, student=s2, issued_by=librarian_user,
            issue_date=today - timedelta(days=4), due_date=today + timedelta(days=10),
        )
        algorithms.available -= 1
        algorithms.save()

        # 3. Returned late with a fine (Tanvir)
        late = BookIssue.objects.create(
            book=clean_code, student=s3, issued_by=librarian_user,
            issue_date=today - timedelta(days=30), due_date=today - timedelta(days=16),
        )
        late.return_date = today - timedelta(days=13)  # 3 days late
        late.status = "RETURNED"
        late.fine = 3 * 5
        late.save()

        # 4. Active issue (Mehdi)
        BookIssue.objects.create(
            book=python_cc, student=s5, issued_by=librarian_user,
            issue_date=today - timedelta(days=9), due_date=today + timedelta(days=5),
        )
        python_cc.available -= 1
        python_cc.save()

        # ------------------------------------------------------------------
        # Payments with demo statuses (today's collection / pending / cancelled)
        # ------------------------------------------------------------------
        Payment.objects.create(
            student=s2, fee_type="EXAM", amount=2500, method="CASH",
            payment_date=today, received_by=cashier_user,
            note="Semester 3 exam fee (in full)",
        )
        # A bank slip the cashier has not verified yet -> PENDING
        Payment.objects.create(
            student=s6, fee_type="EXAM", amount=2400, method="BANK",
            status="PENDING", payment_date=today, received_by=cashier_user,
            note="DBBL deposit slip #D-44102 — awaiting verification",
        )
        # A duplicate entry that was voided -> CANCELLED (ignored in accounts)
        Payment.objects.create(
            student=s8, fee_type="EXAM", amount=2200, method="CARD",
            status="CANCELLED", payment_date=today - timedelta(days=2),
            received_by=cashier_user,
            note="Duplicate card swipe — voided",
        )

        # ------------------------------------------------------------------
        # Notices
        # ------------------------------------------------------------------
        Notice.objects.create(
            title="Final Examination Routine — Fall 2026",
            body="The final examinations for all departments will begin from 20 August 2026. Students are advised to collect their admit cards from the department office before 17 August 2026.",
            audience="ALL", created_by=admin,
        )
        Notice.objects.create(
            title="Semester Fee Payment Deadline",
            body="All students must pay their semester Admission Fee in full by 25 August 2026 (no installments). Students with unpaid admission fees will not be able to pay their exam fee for the final examination.",
            audience="STUDENT", created_by=admin,
        )
        Notice.objects.create(
            title="Result Submission Deadline (Teachers)",
            body="All course teachers are requested to submit in-course marks (out of 40) and final exam marks (out of 60) through the UMS by 30 August 2026.",
            audience="TEACHER", created_by=admin,
        )
        Notice.objects.create(
            title="New Books Added to the Library",
            body="12 new titles on databases, algorithms and electronics are now available in the central library. Students may borrow up to 3 books at a time.",
            audience="ALL", created_by=admin,
        )
        Notice.objects.create(
            title="Library Inventory Reminder",
            body="Please ensure all overdue books are reported to the accounts office so fines can be collected before issuing new books.",
            audience="LIBRARIAN", created_by=admin,
        )
        # Department-scoped notice (visible only inside CSE)
        Notice.objects.create(
            title="CSE Semester 3 — Final Exam Syllabus Announced",
            body="The final exam syllabus for CSE 2101 and CSE 2103 has been finalized. Please contact your course teachers for the chapter list.",
            audience="STUDENT", department=cse, created_by=da_cse.user,
        )

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))
        self.stdout.write(
            "Logins:  admin/admin123 (Super Admin) · D-CSE1/deptadmin123 (Dept Admin) · "
            "T-1001/teacher123 · 2024331501/student123 · L-1001/library123 · C-1001/cashier123"
        )
