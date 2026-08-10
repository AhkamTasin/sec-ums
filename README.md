# University Management System (UMS)

CSE 334 — Database Management System Sessional project,
Sylhet Engineering College, Dept. of CSE.

A University Management System built with **Python (Django)** and a relational
database, following Django's **MVT architecture**.

🚧 **Status: under active development.**

## Planned modules (from the project proposal)

- [x] Custom user model with six roles + role-based access control
- [x] Authentication — login, logout, password change / reset, session security
- [ ] Super Admin panel
- [ ] Department Admin module
- [ ] Teacher module
- [ ] Student module
- [ ] Library module
- [ ] Cashier module

## Tech stack

- Python 3, Django 5
- Django ORM (SQLite for development, MySQL-ready)
- HTML, CSS, Bootstrap 5, JavaScript

## Setup (development)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Run `python manage.py seed_demo` to load demonstration data.
