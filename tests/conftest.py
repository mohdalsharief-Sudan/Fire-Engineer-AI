"""
conftest.py — تهيئة مشتركة لاختبارات FireEngineerAI.

نقطة حرجة: ملف database.py ينشئ محرّك قاعدة البيانات والمجلدات **لحظة
الاستيراد** اعتمادًا على متغيّر البيئة APPDATA. لذلك يجب ضبط APPDATA على
مجلد مؤقّت **قبل** أي استيراد للوحدة، وإلا عملت الاختبارات على قاعدة
بيانات المستخدم الحقيقية وأفسدت بياناته.
"""

import os
import sys
import tempfile

# مجلد مؤقّت للاختبارات — يُضبط قبل استيراد database بأي شكل
_TMP = tempfile.mkdtemp(prefix="fireapp_tests_")
os.environ["APPDATA"] = _TMP

# إتاحة استيراد وحدات المشروع من مجلد الاختبارات
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
import database as db  # noqa: E402


@pytest.fixture
def session():
    """
    جلسة قاعدة بيانات نظيفة لكل اختبار.

    تُنشأ الجداول ثم تُحذف بعد الاختبار، فلا يتسرّب أثر اختبار إلى آخر.
    """
    db.Base.metadata.create_all(db.engine)
    s = db.SessionLocal()
    try:
        yield s
    finally:
        s.close()
        db.Base.metadata.drop_all(db.engine)


@pytest.fixture
def client(session):
    c = db.Client(name="شركة الرياض للمقاولات", phone="0501234567")
    session.add(c)
    session.commit()
    return c


@pytest.fixture
def project(session, client):
    from datetime import date
    p = db.Project(
        name="برج المملكة - نظام الإنذار",
        client_id=client.id, status="Install",
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
    )
    session.add(p)
    session.commit()
    return p
