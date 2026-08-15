"""
migrate_legacy_data.py
استيراد بيانات المشاريع من نسخة قاعدة البيانات القديمة (قبل جدول العملاء
المنفصل) إلى قاعدة البيانات الجديدة.

الاستخدام:
    python migrate_legacy_data.py "C:\\Users\\mohda\\AppData\\Roaming\\FireEngineerAI\\db_legacy_backup_20260809_052450.sqlite3"

إذا لم تحدد مسارًا، سيبحث البرنامج تلقائيًا عن أحدث ملف
db_legacy_backup_*.sqlite3 داخل مجلد بيانات البرنامج ويستخدمه.
"""

import glob
import os
import sqlite3
import sys
from datetime import datetime

from database import get_session, init_db, Client, Project, BASE_DIR


def find_latest_backup():
    pattern = os.path.join(BASE_DIR, "db_legacy_backup_*.sqlite3")
    matches = sorted(glob.glob(pattern), reverse=True)
    return matches[0] if matches else None


def parse_date(value):
    if not value:
        return None
    # SQLite قد يخزن التاريخ كنص "YYYY-MM-DD"
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def migrate(legacy_path):
    if not os.path.exists(legacy_path):
        print(f"خطأ: الملف غير موجود: {legacy_path}")
        return

    print(f"قراءة قاعدة البيانات القديمة: {legacy_path}")
    conn = sqlite3.connect(legacy_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        cur.execute("SELECT * FROM projects")
        legacy_rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        print(f"تعذر قراءة جدول projects من الملف القديم: {e}")
        conn.close()
        return

    print(f"عدد المشاريع الموجودة في النسخة القديمة: {len(legacy_rows)}")

    init_db()  # تأكد من وجود الجداول الجديدة (لن يمسّ أي بيانات موجودة)
    session = get_session()

    # لتفادي الاستيراد المكرر إذا شغّلت السكربت أكثر من مرة
    existing_names = {
        (p.name or "").strip().lower() for p in session.query(Project).all()
    }

    client_cache = {}  # اسم العميل (lowercase) -> Client object

    def get_or_create_client(name):
        name = (name or "").strip()
        if not name:
            return None
        key = name.lower()
        if key in client_cache:
            return client_cache[key]
        existing = session.query(Client).filter(Client.name == name).first()
        if existing:
            client_cache[key] = existing
            return existing
        c = Client(name=name)
        session.add(c)
        session.flush()  # للحصول على c.id قبل الـ commit النهائي
        client_cache[key] = c
        return c

    imported = 0
    skipped = 0

    for row in legacy_rows:
        name = (row["name"] or "").strip()
        if not name:
            continue
        if name.strip().lower() in existing_names:
            skipped += 1
            continue

        client_name = row["client"] if "client" in row.keys() else None
        client_obj = get_or_create_client(client_name)

        p = Project(
            name=name,
            client_id=client_obj.id if client_obj else None,
            site=row["site"] if "site" in row.keys() else None,
            building=row["building"] if "building" in row.keys() else None,
            scope=row["scope"] if "scope" in row.keys() else None,
            standard=row["standard"] if "standard" in row.keys() else None,
            status=row["status"] if "status" in row.keys() else None,
            start_date=parse_date(row["start_date"] if "start_date" in row.keys() else None),
            end_date=parse_date(row["end_date"] if "end_date" in row.keys() else None),
            notes=row["notes"] if "notes" in row.keys() else None,
        )
        session.add(p)
        imported += 1

    session.commit()
    conn.close()

    print("—" * 40)
    print(f"تم استيراد {imported} مشروع بنجاح.")
    if skipped:
        print(f"تم تخطي {skipped} مشروع (موجود مسبقًا بنفس الاسم).")
    print(f"عدد العملاء الذين تم إنشاؤهم/ربطهم: {len(client_cache)}")
    print("ملاحظة: المرفقات القديمة (ATTACHMENTS_DIR) لم تتأثر ولا تزال في مكانها،")
    print("لأن أرقام المشاريع (project id) الجديدة قد تختلف عن القديمة —")
    print("إذا كانت لديك مرفقات مهمة مرتبطة بمشاريع معينة أخبرني للتحقق يدويًا.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        legacy_file = sys.argv[1]
    else:
        legacy_file = find_latest_backup()
        if not legacy_file:
            print("لم يتم العثور على أي ملف db_legacy_backup_*.sqlite3 تلقائيًا.")
            print("مرّر المسار يدويًا:  python migrate_legacy_data.py \"المسار\\db_legacy_backup_....sqlite3\"")
            sys.exit(1)
        print(f"تم العثور على أحدث نسخة احتياطية تلقائيًا: {legacy_file}")

    migrate(legacy_file)
