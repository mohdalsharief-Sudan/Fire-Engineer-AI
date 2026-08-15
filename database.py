"""
database.py
طبقة قاعدة البيانات لبرنامج إدارة مشاريع الحماية من الحريق.
تحتوي على النماذج (Models) وإعداد الاتصال بقاعدة بيانات SQLite عبر SQLAlchemy.
"""

import os
from datetime import date, timedelta

from sqlalchemy import (
    create_engine, Column, Integer, String, Date, Text, Float,
    ForeignKey, or_
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

APP_NAME = "FireEngineerAI"
BASE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
DB_PATH = os.path.join(BASE_DIR, "db.sqlite3")
ATTACHMENTS_DIR = os.path.join(BASE_DIR, "storage", "attachments")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")

for d in (BASE_DIR, ATTACHMENTS_DIR, REPORTS_DIR, BACKUPS_DIR):
    os.makedirs(d, exist_ok=True)

DB_URL = f"sqlite:///{DB_PATH}"
Base = declarative_base()
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    contact_person = Column(String)
    phone = Column(String)
    email = Column(String)
    address = Column(String)
    notes = Column(Text)

    projects = relationship("Project", back_populates="client", cascade="all, delete-orphan")

    @property
    def open_projects_count(self):
        return sum(1 for p in self.projects if p.status != "Handover")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"))
    site = Column(String)
    building = Column(String)
    scope = Column(String)
    standard = Column(String)
    status = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    notes = Column(Text)

    client = relationship("Client", back_populates="projects")
    invoices = relationship("Invoice", back_populates="project", cascade="all, delete-orphan")
    equipment = relationship("Equipment", back_populates="project", cascade="all, delete-orphan")

    @property
    def client_name(self):
        return self.client.name if self.client else ""

    @property
    def total_invoiced(self):
        return sum(i.amount or 0 for i in self.invoices)

    @property
    def total_unpaid(self):
        return sum(i.amount or 0 for i in self.invoices if i.status != "Paid")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    invoice_number = Column(String)
    amount = Column(Float, default=0.0)
    issue_date = Column(Date)
    due_date = Column(Date)
    status = Column(String, default="Unpaid")  # Unpaid, Paid, Overdue
    notes = Column(Text)

    project = relationship("Project", back_populates="invoices")

    @property
    def is_overdue(self):
        return self.status != "Paid" and self.due_date and self.due_date < date.today()


class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    equipment_type = Column(String)   # e.g. Fire Extinguisher, Pump, Panel, Sprinkler Head...
    location = Column(String)
    last_inspection_date = Column(Date)
    interval_days = Column(Integer, default=180)
    status = Column(String, default="OK")  # OK, Needs Attention, Faulty
    notes = Column(Text)

    project = relationship("Project", back_populates="equipment")

    @property
    def next_inspection_date(self):
        if self.last_inspection_date and self.interval_days:
            return self.last_inspection_date + timedelta(days=self.interval_days)
        return None

    @property
    def days_until_due(self):
        nxt = self.next_inspection_date
        if not nxt:
            return None
        return (nxt - date.today()).days

    @property
    def alert_level(self):
        """none | soon | overdue"""
        d = self.days_until_due
        if d is None:
            return "none"
        if d < 0:
            return "overdue"
        if d <= 30:
            return "soon"
        return "none"


def _needs_legacy_migration():
    """
    يتحقق مما إذا كانت قاعدة البيانات الحالية من النسخة القديمة (قبل إضافة
    جدول العملاء والفواتير والمعدات)، حيث كان عمود "client" نصًا حرًا بدل
    ربط بجدول Client عبر client_id.
    """
    if not os.path.exists(DB_PATH):
        return False
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(projects)")
        cols = [row[1] for row in cur.fetchall()]
        conn.close()
        # قاعدة بيانات قديمة: يوجد عمود "client" نصي ولا يوجد "client_id"
        return "client" in cols and "client_id" not in cols
    except Exception:
        return False


def init_db():
    """
    يهيئ قاعدة البيانات. إذا كانت قاعدة بيانات قديمة (من نسخة سابقة للبرنامج
    بدون جدول عملاء منفصل)، تُنسخ احتياطيًا تلقائيًا تحت اسم مختلف قبل إنشاء
    الجداول الجديدة، حتى لا تُفقد أي بيانات ولا يتعطل البرنامج بسبب اختلاف
    البنية (schema).
    """
    if _needs_legacy_migration():
        import shutil as _shutil
        from datetime import datetime as _dt
        stamp = _dt.now().strftime("%Y%m%d_%H%M%S")
        legacy_backup = os.path.join(BASE_DIR, f"db_legacy_backup_{stamp}.sqlite3")
        try:
            _shutil.copy2(DB_PATH, legacy_backup)
            os.remove(DB_PATH)
            print(
                "تنبيه: تم اكتشاف قاعدة بيانات من نسخة سابقة للبرنامج. "
                f"تم حفظ نسخة منها هنا:\n{legacy_backup}\n"
                "سيتم إنشاء قاعدة بيانات جديدة بالبنية المحدثة (تحتوي على "
                "العملاء والفواتير والمعدات). يمكنك استيراد بياناتك القديمة "
                "يدويًا إن رغبت."
            )
        except Exception as e:
            print("تعذر ترحيل قاعدة البيانات القديمة تلقائيًا:", e)

    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()


# ---------------------------------------------------------------------------
# Shared query helpers
# ---------------------------------------------------------------------------

def search_projects(session, text="", status="", client_id=None):
    q = session.query(Project)
    if text:
        like = f"%{text}%"
        q = q.filter(or_(
            Project.name.ilike(like),
            Project.site.ilike(like),
            Project.building.ilike(like),
            Project.scope.ilike(like),
            Project.standard.ilike(like),
            Project.status.ilike(like),
            Project.notes.ilike(like),
        ))
    if status:
        q = q.filter(Project.status == status)
    if client_id:
        q = q.filter(Project.client_id == client_id)
    return q.order_by(Project.id.desc()).all()


def upcoming_inspections(session, within_days=30):
    """Equipment whose next inspection is overdue or due within `within_days`."""
    items = session.query(Equipment).all()
    out = []
    for e in items:
        if e.alert_level in ("soon", "overdue"):
            out.append(e)
    out.sort(key=lambda e: (e.days_until_due is None, e.days_until_due))
    return out


def unpaid_invoices(session):
    return session.query(Invoice).filter(Invoice.status != "Paid").order_by(Invoice.due_date.asc()).all()


def dashboard_stats(session):
    projects = session.query(Project).all()
    status_counts = {}
    for p in projects:
        status_counts[p.status or "Unknown"] = status_counts.get(p.status or "Unknown", 0) + 1

    invoices = session.query(Invoice).all()
    total_invoiced = sum(i.amount or 0 for i in invoices)
    total_unpaid = sum(i.amount or 0 for i in invoices if i.status != "Paid")
    overdue_count = sum(1 for i in invoices if i.is_overdue)

    equip_alerts = upcoming_inspections(session)

    return {
        "total_projects": len(projects),
        "status_counts": status_counts,
        "total_clients": session.query(Client).count(),
        "total_invoiced": total_invoiced,
        "total_unpaid": total_unpaid,
        "overdue_invoices": overdue_count,
        "equipment_alerts": equip_alerts,
    }
