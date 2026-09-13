# -*- coding: utf-8 -*-
"""
نظام إدارة مدرسة الهدى الثانوية بنين - تطبيق أندرويد أوفلاين بتقنية Flet
Fully offline native Android app built with Flet (Flutter + Python).

Why Flet instead of the previous Kivy/Buildozer attempt:
- Flet builds on Flutter's own mature Android build pipeline (flet build apk),
  so there is no separate python-for-android/Buildozer/Gradle stack to fight.
- Flet has native right-to-left (page.rtl = True) support, so Arabic text
  renders and aligns correctly without manual reshaping tricks.
- There is still no web server and no WebView involved - this is a native
  Flutter UI talking directly to a bundled Python process on the device.

Data is stored in a local SQLite file inside FLET_APP_STORAGE_DATA, which is
the app's private, durable, offline storage folder on the device - no
internet connection is ever required.
"""

import os
import sqlite3
from datetime import date

import flet as ft

FONT_NAME = "Amiri"


# ---------------------------------------------------------------------------
# Database layer (plain sqlite3 - no web framework, no server)
# ---------------------------------------------------------------------------
class DB:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject_id INTEGER,
                phone TEXT,
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
            );
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                class_id INTEGER,
                phone TEXT,
                guardian_phone TEXT,
                FOREIGN KEY(class_id) REFERENCES classes(id)
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                att_date TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id)
            );
            CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                term TEXT,
                score REAL,
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
            );
            CREATE TABLE IF NOT EXISTS fees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                amount REAL,
                paid REAL DEFAULT 0,
                fee_date TEXT,
                FOREIGN KEY(student_id) REFERENCES students(id)
            );
            """
        )
        self.conn.commit()

    def fetchall(self, q, params=()):
        return self.conn.execute(q, params).fetchall()

    def execute(self, q, params=()):
        cur = self.conn.execute(q, params)
        self.conn.commit()
        return cur.lastrowid

    # classes
    def add_class(self, name):
        return self.execute("INSERT INTO classes(name) VALUES (?)", (name,))

    def list_classes(self):
        return self.fetchall("SELECT id, name FROM classes ORDER BY name")

    def delete_class(self, cid):
        self.execute("DELETE FROM classes WHERE id=?", (cid,))

    # subjects
    def add_subject(self, name):
        return self.execute("INSERT INTO subjects(name) VALUES (?)", (name,))

    def list_subjects(self):
        return self.fetchall("SELECT id, name FROM subjects ORDER BY name")

    def delete_subject(self, sid):
        self.execute("DELETE FROM subjects WHERE id=?", (sid,))

    # teachers
    def add_teacher(self, name, subject_id, phone):
        return self.execute(
            "INSERT INTO teachers(name, subject_id, phone) VALUES (?,?,?)",
            (name, subject_id, phone),
        )

    def list_teachers(self):
        return self.fetchall(
            """SELECT teachers.id, teachers.name,
                      COALESCE(subjects.name, ''), teachers.phone
               FROM teachers LEFT JOIN subjects ON teachers.subject_id = subjects.id
               ORDER BY teachers.name"""
        )

    def delete_teacher(self, tid):
        self.execute("DELETE FROM teachers WHERE id=?", (tid,))

    # students
    def add_student(self, name, class_id, phone, guardian_phone):
        return self.execute(
            "INSERT INTO students(name, class_id, phone, guardian_phone) VALUES (?,?,?,?)",
            (name, class_id, phone, guardian_phone),
        )

    def list_students(self):
        return self.fetchall(
            """SELECT students.id, students.name, COALESCE(classes.name,''),
                      students.phone, students.guardian_phone
               FROM students LEFT JOIN classes ON students.class_id = classes.id
               ORDER BY students.name"""
        )

    def delete_student(self, sid):
        self.execute("DELETE FROM students WHERE id=?", (sid,))

    # attendance
    def mark_attendance(self, student_id, att_date, status):
        self.execute(
            "INSERT INTO attendance(student_id, att_date, status) VALUES (?,?,?)",
            (student_id, att_date, status),
        )

    def list_attendance(self):
        return self.fetchall(
            """SELECT attendance.id, students.name, attendance.att_date, attendance.status
               FROM attendance JOIN students ON attendance.student_id = students.id
               ORDER BY attendance.att_date DESC"""
        )

    # grades
    def add_grade(self, student_id, subject_id, term, score):
        self.execute(
            "INSERT INTO grades(student_id, subject_id, term, score) VALUES (?,?,?,?)",
            (student_id, subject_id, term, score),
        )

    def list_grades(self):
        return self.fetchall(
            """SELECT grades.id, students.name, subjects.name, grades.term, grades.score
               FROM grades JOIN students ON grades.student_id = students.id
               JOIN subjects ON grades.subject_id = subjects.id
               ORDER BY students.name"""
        )

    # fees
    def add_fee(self, student_id, amount, paid, fee_date):
        self.execute(
            "INSERT INTO fees(student_id, amount, paid, fee_date) VALUES (?,?,?,?)",
            (student_id, amount, paid, fee_date),
        )

    def list_fees(self):
        return self.fetchall(
            """SELECT fees.id, students.name, fees.amount, fees.paid, fees.fee_date
               FROM fees JOIN students ON fees.student_id = students.id
               ORDER BY fees.fee_date DESC"""
        )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
def main(page: ft.Page):
    page.title = "مدرسة الهدى الثانوية بنين"
    page.rtl = True
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT
    try:
        page.fonts = {FONT_NAME: "fonts/Amiri-Regular.ttf"}
        page.theme = ft.Theme(font_family=FONT_NAME)
    except Exception:
        pass  # font file not bundled yet -> falls back to the default font

    data_dir = os.environ.get("FLET_APP_STORAGE_DATA", ".")
    os.makedirs(data_dir, exist_ok=True)
    db = DB(os.path.join(data_dir, "school.db"))

    def snackbar(msg):
        page.open(ft.SnackBar(content=ft.Text(msg, text_align=ft.TextAlign.RIGHT)))

    def safe_delete(delete_fn, item_id, refresh_fn):
        try:
            delete_fn(item_id)
        except sqlite3.IntegrityError:
            snackbar("لا يمكن حذف هذا العنصر لأنه مرتبط ببيانات أخرى (مثل طلاب أو درجات مسجلة عليه)")
        refresh_fn()

    def screen_container(title, body_controls, on_back):
        return ft.Column(
            expand=True,
            controls=[
                ft.Container(
                    padding=ft.padding.Padding(top=40, bottom=10, left=10, right=10),
                    bgcolor=ft.Colors.BLUE_700,
                    content=ft.Row(
                        controls=[
                            ft.TextButton(
                                "رجوع",
                                icon=ft.Icons.ARROW_FORWARD,
                                on_click=lambda e: on_back(),
                                style=ft.ButtonStyle(color=ft.Colors.WHITE),
                            ),
                            ft.Text(
                                title,
                                size=20,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                                expand=True,
                                text_align=ft.TextAlign.RIGHT,
                            ),
                        ]
                    ),
                ),
                ft.Container(
                    padding=15,
                    expand=True,
                    content=ft.Column(controls=body_controls, expand=True, spacing=10),
                ),
            ],
        )

    # -------------------------------------------------------------- menu
    def show_menu():
        page.controls.clear()
        items = [
            ("الطلاب", show_students),
            ("المعلمون", show_teachers),
            ("الفصول", show_classes),
            ("المواد الدراسية", show_subjects),
            ("الحضور والغياب", show_attendance),
            ("الدرجات", show_grades),
            ("الرسوم الدراسية", show_fees),
        ]
        buttons = [
            ft.ElevatedButton(
                content=label,
                on_click=lambda e, fn=fn: fn(),
                width=320,
                height=56,
            )
            for label, fn in items
        ]
        page.add(
            ft.Column(
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Container(height=30),
                    ft.Text(
                        "نظام إدارة مدرسة الهدى الثانوية بنين",
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=20),
                    *buttons,
                ],
            )
        )
        page.update()

    # ---------------------------------------------------------- classes
    def show_classes():
        name_field = ft.TextField(label="اسم الفصل", text_align=ft.TextAlign.RIGHT)
        list_col = ft.Column(spacing=4)

        def refresh():
            list_col.controls.clear()
            for cid, name in db.list_classes():
                list_col.controls.append(
                    ft.Row(
                        controls=[
                            ft.Text(name, expand=True, text_align=ft.TextAlign.RIGHT),
                            ft.IconButton(
                                ft.Icons.DELETE, icon_color=ft.Colors.RED,
                                on_click=lambda e, i=cid: safe_delete(db.delete_class, i, refresh),
                            ),
                        ]
                    )
                )
            page.update()

        def add_class(e):
            if not name_field.value:
                return
            db.add_class(name_field.value.strip())
            name_field.value = ""
            refresh()

        body = [
            ft.Row(controls=[name_field, ft.ElevatedButton("إضافة", on_click=add_class)]),
            ft.Divider(),
            ft.Container(content=list_col, expand=True),
        ]
        page.controls.clear()
        page.add(screen_container("إدارة الفصول", body, show_menu))
        refresh()

    # --------------------------------------------------------- subjects
    def show_subjects():
        name_field = ft.TextField(label="اسم المادة", text_align=ft.TextAlign.RIGHT)
        list_col = ft.Column(spacing=4)

        def refresh():
            list_col.controls.clear()
            for sid, name in db.list_subjects():
                list_col.controls.append(
                    ft.Row(
                        controls=[
                            ft.Text(name, expand=True, text_align=ft.TextAlign.RIGHT),
                            ft.IconButton(
                                ft.Icons.DELETE, icon_color=ft.Colors.RED,
                                on_click=lambda e, i=sid: safe_delete(db.delete_subject, i, refresh),
                            ),
                        ]
                    )
                )
            page.update()

        def add_subject(e):
            if not name_field.value:
                return
            db.add_subject(name_field.value.strip())
            name_field.value = ""
            refresh()

        body = [
            ft.Row(controls=[name_field, ft.ElevatedButton("إضافة", on_click=add_subject)]),
            ft.Divider(),
            ft.Container(content=list_col, expand=True),
        ]
        page.controls.clear()
        page.add(screen_container("إدارة المواد الدراسية", body, show_menu))
        refresh()

    # --------------------------------------------------------- teachers
    def show_teachers():
        subjects = db.list_subjects()
        name_field = ft.TextField(label="اسم المعلم", text_align=ft.TextAlign.RIGHT)
        phone_field = ft.TextField(label="رقم الهاتف", text_align=ft.TextAlign.RIGHT)
        subject_dd = ft.Dropdown(
            label="المادة",
            options=[ft.dropdown.Option(key=str(sid), text=name) for sid, name in subjects],
        )
        list_col = ft.Column(spacing=4)

        def refresh():
            list_col.controls.clear()
            for tid, name, subject_name, phone in db.list_teachers():
                list_col.controls.append(
                    ft.Row(
                        controls=[
                            ft.Text(
                                f"{name} - {subject_name} - {phone}",
                                expand=True, text_align=ft.TextAlign.RIGHT,
                            ),
                            ft.IconButton(
                                ft.Icons.DELETE, icon_color=ft.Colors.RED,
                                on_click=lambda e, i=tid: safe_delete(db.delete_teacher, i, refresh),
                            ),
                        ]
                    )
                )
            page.update()

        def add_teacher(e):
            if not name_field.value:
                return
            subject_id = int(subject_dd.value) if subject_dd.value else None
            db.add_teacher(name_field.value.strip(), subject_id, phone_field.value.strip())
            name_field.value = ""
            phone_field.value = ""
            refresh()

        body = [
            name_field, phone_field, subject_dd,
            ft.ElevatedButton("إضافة معلم", on_click=add_teacher),
            ft.Divider(),
            ft.Container(content=list_col, expand=True),
        ]
        page.controls.clear()
        page.add(screen_container("إدارة المعلمين", body, show_menu))
        refresh()

    # --------------------------------------------------------- students
    def show_students():
        classes = db.list_classes()
        name_field = ft.TextField(label="اسم الطالب", text_align=ft.TextAlign.RIGHT)
        phone_field = ft.TextField(label="رقم هاتف الطالب", text_align=ft.TextAlign.RIGHT)
        guardian_field = ft.TextField(label="رقم هاتف ولي الأمر", text_align=ft.TextAlign.RIGHT)
        class_dd = ft.Dropdown(
            label="الفصل",
            options=[ft.dropdown.Option(key=str(cid), text=name) for cid, name in classes],
        )
        list_col = ft.Column(spacing=4)

        def refresh():
            list_col.controls.clear()
            for sid, name, class_name, phone, guardian in db.list_students():
                list_col.controls.append(
                    ft.Row(
                        controls=[
                            ft.Text(f"{name} - {class_name}", expand=True, text_align=ft.TextAlign.RIGHT),
                            ft.IconButton(
                                ft.Icons.DELETE, icon_color=ft.Colors.RED,
                                on_click=lambda e, i=sid: safe_delete(db.delete_student, i, refresh),
                            ),
                        ]
                    )
                )
            page.update()

        def add_student(e):
            if not name_field.value:
                return
            class_id = int(class_dd.value) if class_dd.value else None
            db.add_student(
                name_field.value.strip(), class_id,
                phone_field.value.strip(), guardian_field.value.strip(),
            )
            name_field.value = ""
            phone_field.value = ""
            guardian_field.value = ""
            refresh()

        body = [
            name_field, phone_field, guardian_field, class_dd,
            ft.ElevatedButton("إضافة طالب", on_click=add_student),
            ft.Divider(),
            ft.Container(content=list_col, expand=True),
        ]
        page.controls.clear()
        page.add(screen_container("إدارة الطلاب", body, show_menu))
        refresh()

    # ------------------------------------------------------- attendance
    def show_attendance():
        students = db.list_students()
        student_dd = ft.Dropdown(
            label="الطالب",
            options=[ft.dropdown.Option(key=str(sid), text=name) for sid, name, *_ in students],
        )
        date_field = ft.TextField(label="التاريخ (YYYY-MM-DD)", value=date.today().isoformat(), text_align=ft.TextAlign.RIGHT)
        status_dd = ft.Dropdown(
            label="الحالة",
            value="حاضر",
            options=[ft.dropdown.Option(key=s, text=s) for s in ["حاضر", "غائب", "متأخر"]],
        )
        list_col = ft.Column(spacing=4)

        def refresh():
            list_col.controls.clear()
            for rid, name, att_date, status in db.list_attendance():
                list_col.controls.append(
                    ft.Text(f"{name} - {att_date} - {status}", text_align=ft.TextAlign.RIGHT)
                )
            page.update()

        def add_att(e):
            if not student_dd.value:
                return
            db.mark_attendance(int(student_dd.value), date_field.value.strip(), status_dd.value)
            refresh()

        body = [
            student_dd, date_field, status_dd,
            ft.ElevatedButton("تسجيل", on_click=add_att),
            ft.Divider(),
            ft.Container(content=list_col, expand=True),
        ]
        page.controls.clear()
        page.add(screen_container("الحضور والغياب", body, show_menu))
        refresh()

    # ----------------------------------------------------------- grades
    def show_grades():
        students = db.list_students()
        subjects = db.list_subjects()
        student_dd = ft.Dropdown(
            label="الطالب",
            options=[ft.dropdown.Option(key=str(sid), text=name) for sid, name, *_ in students],
        )
        subject_dd = ft.Dropdown(
            label="المادة",
            options=[ft.dropdown.Option(key=str(sid), text=name) for sid, name in subjects],
        )
        term_field = ft.TextField(label="الفصل الدراسي (مثال: الأول)", text_align=ft.TextAlign.RIGHT)
        score_field = ft.TextField(label="الدرجة", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.RIGHT)
        list_col = ft.Column(spacing=4)

        def refresh():
            list_col.controls.clear()
            for rid, sname, subname, term, score in db.list_grades():
                list_col.controls.append(
                    ft.Text(f"{sname} - {subname} - {term} - {score}", text_align=ft.TextAlign.RIGHT)
                )
            page.update()

        def add_grade(e):
            if not student_dd.value or not subject_dd.value:
                return
            try:
                score = float(score_field.value)
            except (TypeError, ValueError):
                snackbar("الرجاء إدخال درجة رقمية صحيحة")
                return
            db.add_grade(int(student_dd.value), int(subject_dd.value), term_field.value.strip(), score)
            score_field.value = ""
            refresh()

        body = [
            student_dd, subject_dd, term_field, score_field,
            ft.ElevatedButton("إضافة درجة", on_click=add_grade),
            ft.Divider(),
            ft.Container(content=list_col, expand=True),
        ]
        page.controls.clear()
        page.add(screen_container("الدرجات", body, show_menu))
        refresh()

    # ------------------------------------------------------------- fees
    def show_fees():
        students = db.list_students()
        student_dd = ft.Dropdown(
            label="الطالب",
            options=[ft.dropdown.Option(key=str(sid), text=name) for sid, name, *_ in students],
        )
        amount_field = ft.TextField(label="المبلغ المطلوب", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.RIGHT)
        paid_field = ft.TextField(label="المبلغ المدفوع", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.RIGHT)
        date_field = ft.TextField(label="التاريخ (YYYY-MM-DD)", value=date.today().isoformat(), text_align=ft.TextAlign.RIGHT)
        list_col = ft.Column(spacing=4)

        def refresh():
            list_col.controls.clear()
            for rid, name, amount, paid, fee_date in db.list_fees():
                remaining = amount - paid
                list_col.controls.append(
                    ft.Text(
                        f"{name} - المطلوب:{amount} - المدفوع:{paid} - المتبقي:{remaining} - {fee_date}",
                        text_align=ft.TextAlign.RIGHT,
                    )
                )
            page.update()

        def add_fee(e):
            if not student_dd.value:
                return
            try:
                amount = float(amount_field.value or 0)
                paid = float(paid_field.value or 0)
            except ValueError:
                snackbar("الرجاء إدخال أرقام صحيحة")
                return
            db.add_fee(int(student_dd.value), amount, paid, date_field.value.strip())
            amount_field.value = ""
            paid_field.value = ""
            refresh()

        body = [
            student_dd, amount_field, paid_field, date_field,
            ft.ElevatedButton("تسجيل", on_click=add_fee),
            ft.Divider(),
            ft.Container(content=list_col, expand=True),
        ]
        page.controls.clear()
        page.add(screen_container("الرسوم الدراسية", body, show_menu))
        refresh()

    show_menu()


if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
