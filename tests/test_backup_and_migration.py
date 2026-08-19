"""
اختبارات النسخ الاحتياطي وترحيل بنية قاعدة البيانات.

هذه أخطر أجزاء البرنامج: خلل في النسخ = فقدان بيانات، وخلل في الترحيل =
برنامج لا يفتح على قاعدة بيانات قديمة.
"""

import os
import sqlite3

import applog


def _make_db(path, rows=3):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT)")
    for i in range(rows):
        conn.execute("INSERT INTO clients (name) VALUES (?)", (f"عميل {i}",))
    conn.commit()
    conn.close()


class TestBackup:

    def test_creates_verified_backup(self, tmp_path):
        db = tmp_path / "db.sqlite3"
        backups = tmp_path / "backups"
        _make_db(str(db))

        ok, dest = applog.create_backup(str(db), str(backups))
        assert ok is True
        assert os.path.exists(dest)
        assert applog.verify_backup(dest) is True

    def test_backup_preserves_data(self, tmp_path):
        db = tmp_path / "db.sqlite3"
        _make_db(str(db), rows=5)
        ok, dest = applog.create_backup(str(db), str(tmp_path / "b"))

        conn = sqlite3.connect(dest)
        count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        conn.close()
        assert count == 5

    def test_two_backups_same_second_do_not_overwrite(self, tmp_path):
        """
        الخلل الأصلي: الاسم بالتاريخ فقط، فنسخة ثانية في اليوم نفسه تمحو
        الأولى. وحتى بعد إضافة الوقت بالثانية بقي التصادم ممكنًا حين تقع
        نسختان في الثانية نفسها (النسخة التلقائية ثم ضغطة يدوية فورية).
        """
        db = tmp_path / "db.sqlite3"
        backups = tmp_path / "backups"
        _make_db(str(db))

        paths = [applog.create_backup(str(db), str(backups))[1] for _ in range(5)]

        assert len(set(paths)) == 5, "أسماء متكرّرة — نسخة محت أخرى"
        assert len(os.listdir(backups)) == 5

    def test_prune_keeps_newest_only(self, tmp_path):
        db = tmp_path / "db.sqlite3"
        backups = tmp_path / "backups"
        _make_db(str(db))

        for _ in range(6):
            applog.create_backup(str(db), str(backups), keep=3)

        assert len(os.listdir(backups)) == 3

    def test_missing_database_reports_failure(self, tmp_path):
        ok, msg = applog.create_backup(str(tmp_path / "لا-يوجد.sqlite3"),
                                       str(tmp_path / "b"))
        assert ok is False
        assert isinstance(msg, str) and msg

    def test_corrupt_file_fails_verification(self, tmp_path):
        bad = tmp_path / "bad.sqlite3"
        bad.write_bytes(b"not a database")
        assert applog.verify_backup(str(bad)) is False

    def test_auto_backup_runs_once_per_day(self, tmp_path):
        db = tmp_path / "db.sqlite3"
        backups = tmp_path / "backups"
        _make_db(str(db))

        first = applog.auto_backup_on_start(str(db), str(backups))
        second = applog.auto_backup_on_start(str(db), str(backups))

        assert first is not None
        assert second is None, "أنشأ نسخة تلقائية ثانية في اليوم نفسه"


class TestMigration:
    """
    create_all() ينشئ الجداول الناقصة فقط ولا يضيف عمودًا إلى جدول قائم.
    بدون الترحيل يفشل البرنامج على قاعدة بيانات المستخدم الحالية بخطأ
    "no such column: invoices.contract_id".
    """

    def test_adds_missing_column_to_existing_table(self, tmp_path, monkeypatch):
        import importlib
        import sqlalchemy

        db_path = tmp_path / "old.sqlite3"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT,
                                   client_id INTEGER);
            CREATE TABLE invoices (id INTEGER PRIMARY KEY, project_id INTEGER,
                                   invoice_number TEXT, amount FLOAT,
                                   status TEXT);
            INSERT INTO clients (name) VALUES ('عميل قديم');
            INSERT INTO projects (name, client_id) VALUES ('مشروع قديم', 1);
            INSERT INTO invoices (project_id, invoice_number, amount, status)
                VALUES (1, 'INV-OLD', 5000, 'Unpaid');
        """)
        conn.commit()
        conn.close()

        before = [r[1] for r in sqlite3.connect(str(db_path))
                  .execute("PRAGMA table_info(invoices)")]
        assert "contract_id" not in before

        import database as db
        engine = sqlalchemy.create_engine(f"sqlite:///{db_path}", future=True)
        monkeypatch.setattr(db, "engine", engine)
        db._migrate_add_columns()

        after = [r[1] for r in sqlite3.connect(str(db_path))
                 .execute("PRAGMA table_info(invoices)")]
        assert "contract_id" in after

        # البيانات القديمة سليمة
        conn = sqlite3.connect(str(db_path))
        assert conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 1
        assert conn.execute(
            "SELECT invoice_number FROM invoices").fetchone()[0] == "INV-OLD"
        conn.close()

    def test_migration_is_idempotent(self, tmp_path, monkeypatch):
        """تشغيله مرتين يجب ألا يفشل (يحدث عند كل إقلاع)."""
        import sqlalchemy
        import database as db

        db_path = tmp_path / "x.sqlite3"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE invoices (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        engine = sqlalchemy.create_engine(f"sqlite:///{db_path}", future=True)
        monkeypatch.setattr(db, "engine", engine)
        db._migrate_add_columns()
        db._migrate_add_columns()  # لا يجب أن يرمي استثناء


class TestVersion:

    def test_version_is_defined(self):
        assert applog.__version__
        assert applog.__version__.count(".") == 2
