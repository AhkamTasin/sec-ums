# 🎓 SEC UMS — Beginner's Local Setup Guide

**Sylhet Engineering College — University Management System (SEC UMS)**

This guide takes you from *zero* to the app running on your own laptop.
It assumes **Windows** (notes for macOS/Linux at the bottom).
No prior programming experience needed — just follow each step in order.

---

## What you're going to do (overview)

1. Install Python (one time)
2. Extract the project zip
3. Install 3 small libraries (`pip install -r requirements.txt`)
4. Create the database tables (`migrate`)
5. Load demo data (`seed_demo`)
6. Start the server and open `http://127.0.0.1:8000`

> ⏱️ About 10 minutes total. There is also a **one-click script** (Step 3, easy way).

---

## Step 1 — Download & extract the project

1. Download **`ums_project.zip`**.
2. Right-click it → **Extract All…** → extract to somewhere easy to find,
   e.g. `Desktop` or `Documents`.
3. You now have a folder called **`ums_project`**. Open it — you should see
   files like `manage.py`, `requirements.txt`, `run_windows.bat`, and folders
   (`accounts`, `academics`, `fees`, `library`, `templates`, `static`, …).

## Step 2 — Install Python (one time)

1. Go to **<https://www.python.org/downloads/>** and click the big
   **Download Python 3.x** button (any version **3.10 or newer** works;
   3.12/3.13 is perfect).
2. Run the downloaded installer.
3. ⚠️ **On the very first screen, tick the checkbox
   “Add python.exe to PATH”** — this is the #1 thing beginners forget.
4. Click **Install Now** and finish.

**Check it worked:** press `Win + R` → type `cmd` → Enter. In the black
window (Command Prompt) type:

```
python --version
```

You should see something like `Python 3.12.5`.

> If Windows says *"'python' is not recognized"* — re-run the installer and
> tick the PATH box, **or** just use `py` instead of `python` in every
> command below (`py` is installed by the official installer).

## Step 3 — Install the libraries

Open Command Prompt **inside the project folder**:
open the `ums_project` folder in Explorer, click the address bar, type
`cmd`, press Enter. Then run:

```
pip install -r requirements.txt
```

This installs exactly three things (needs internet **once**):

| Package | Used for |
|---|---|
| **Django** | the web framework the app is built with |
| **Pillow** | book-cover images in the library |
| **ReportLab** | the PDF result sheet (transcript) |

### ✨ Easy way instead of Steps 3–6

Just **double-click `run_windows.bat`** inside the project folder.
It does everything below automatically and starts the server.
*(There's also `run_mac_linux.sh` for mac/Linux.)*

## Step 4 — Create the database (one time)

```
python manage.py migrate
```

This creates all the tables (users, students, courses, results, payments,
books, …) in the bundled **`db.sqlite3`** file — no database server needed.

> The zip already includes a ready `db.sqlite3`, so this step usually just
> says “No migrations to apply”. Harmless either way.

## Step 5 — Load the demo data (one time)

```
python manage.py seed_demo
```

This fills the database with 3 departments, 8 students, 4 teachers,
courses with results, fees & payments, 12 library books (it even draws
their cover images), notices and more — so every screen has real content.

> If it says *“Data already exists — skipping seed”*, that's fine —
> the zip ships with the demo data pre-loaded.

## Step 6 — Start the server

```
python manage.py runserver
```

You'll see:

```
Starting development server at http://127.0.0.1:8000/
```

**Leave this window open** — it *is* the website.

## Step 7 — Open the app

In your browser go to:

```
http://127.0.0.1:8000
```

- `/` is the **college landing page** — click **Portal Login** (top-right).
- Sign in with any demo account (they're also clickable chips on the login page):

| Role | Username | Password | What to try first |
|---|---|---|---|
| Super Admin | `admin` | `admin123` | Departments, dept admins, all-user analytics |
| Dept Admin (CSE) | `D-CSE1` | `deptadmin123` | Students, results review & publish |
| Teacher | `T-1001` | `teacher123` | Attendance, materials, in-course marks |
| Student | `2024331501` | `student123` | Dashboard, results + **PDF transcript** |
| Librarian | `L-1001` | `library123` | Bookstore catalogue, issue/return, library card |
| Cashier | `C-1001` | `cashier123` | Receive payment → **printable receipt**, daily report |

**Nice demo touches:** the moon/sun icon in the top bar switches
**dark ↔ light mode**, and the bell icon shows live notifications.

## Step 8 — Stop & start later

- **Stop:** click the server window, press `Ctrl + C` (or close it).
- **Start again:** run `python manage.py runserver` (or double-click
  `run_windows.bat`) — your data persists in `db.sqlite3`.

---

## 🍎 macOS / Linux

Same flow in the Terminal:

```bash
cd ums_project
python3 -m pip install -r requirements.txt
python3 manage.py migrate
python3 manage.py seed_demo
python3 manage.py runserver
```

or simply `bash run_mac_linux.sh`. Then open <http://127.0.0.1:8000>.

> If `python3` is missing on a Mac: install it from python.org, or
> `brew install python` if you use Homebrew.

---

## ❗ Troubleshooting

| Problem | Fix |
|---|---|
| `'python' is not recognized…` | Reinstall Python and **tick “Add python.exe to PATH”**, or use `py` instead of `python`. |
| `No module named 'django'` | Run `pip install -r requirements.txt` in the project folder, in the *same* window you start the server from. |
| pip fails / TLS errors / very old | `python -m pip install --upgrade pip` then retry. |
| Pillow won't install | Upgrade pip first (above). Any Python 3.10+ has prebuilt wheels, so it normally “just works”. |
| `That port is already in use` | Another server is running — close it, **or** use `python manage.py runserver 8001` and open `http://127.0.0.1:8001`. |
| Page is blank/menu-less | You're not logged in — every dashboard needs a role account (table above). |
| Forgot admin password / broke the data | `python manage.py flush` then `python manage.py seed_demo` → fresh demo database. |
| Browser says “can't reach this site” | Make sure the server window is still open and shows no errors. |

---

## 🗄️ Optional — run on MySQL (as in the project proposal)

SQLite works perfectly for development. To use MySQL instead:

1. Install MySQL Server and create a database:

   ```sql
   CREATE DATABASE ums_db CHARACTER SET utf8mb4;
   ```

2. Install the driver: `pip install mysqlclient`
3. Set environment variables, then migrate & seed:

   **Windows (Command Prompt):**
   ```
   set USE_MYSQL=1 & set MYSQL_NAME=ums_db & set MYSQL_USER=root & set MYSQL_PASSWORD=yourpass & python manage.py migrate & python manage.py seed_demo & python manage.py runserver
   ```

   **macOS/Linux:**
   ```bash
   USE_MYSQL=1 MYSQL_NAME=ums_db MYSQL_USER=root MYSQL_PASSWORD=yourpass python3 manage.py migrate
   USE_MYSQL=1 MYSQL_NAME=ums_db MYSQL_USER=root MYSQL_PASSWORD=yourpass python3 manage.py seed_demo
   USE_MYSQL=1 MYSQL_NAME=ums_db MYSQL_USER=root MYSQL_PASSWORD=yourpass python3 manage.py runserver
   ```

## 🧑‍💻 Editing the code (optional)

Use **VS Code** (as in the project proposal): *File → Open Folder…* → pick
`ums_project`. Open the built-in terminal with `` Ctrl + ` `` — the same
commands work there. The server auto-reloads when you save Python file
changes (when started without `--noreload`).
