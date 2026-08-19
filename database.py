"""
database.py
طبقة قاعدة البيانات لبرنامج إدارة مشاريع الحماية من الحريق.
تحتوي على النماذج (Models) وإعداد الاتصال بقاعدة بيانات SQLite عبر SQLAlchemy.
"""

import os
from datetime import date, timedelta

from sqlalchemy import (
    create_engine, Column, Integer, String, Date, Text, Float, event,
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


# SQLite يتجاهل قيود المفاتيح الأجنبية (ومنها ON DELETE SET NULL) ما لم تُفعَّل
# صراحةً لكل اتصال. بدون هذا السطر يبقى client_id مشيرًا لعميل محذوف.
@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


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

    # ملاحظة مهمة: كانت هنا cascade="all, delete-orphan" وهذا يعني أن حذف عميل
    # يحذف كل مشاريعه (وبالتالي فواتيرها ومعداتها) بصمت — خطر فقدان بيانات.
    # الآن: عند حذف العميل تبقى المشاريع ويصبح client_id = NULL.
    projects = relationship("Project", back_populates="client", passive_deletes=True)
    # حذف العميل لا يحذف عقوده — يصبح client_id = NULL (نفس منطق المشاريع)
    contracts = relationship("Contract", back_populates="client", passive_deletes=True)

    @property
    def open_projects_count(self):
        return sum(1 for p in self.projects if p.status != "Handover")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"))
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
    contracts = relationship("Contract", back_populates="project", passive_deletes=True)

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
    # فاتورة عقد صيانة (اختياري) — تبقى الفاتورة مرتبطة بالمشروع كما هي
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="SET NULL"))
    invoice_number = Column(String)
    amount = Column(Float, default=0.0)
    issue_date = Column(Date)
    due_date = Column(Date)
    status = Column(String, default="Unpaid")  # Unpaid, Paid, Overdue
    notes = Column(Text)

    project = relationship("Project", back_populates="invoices")
    contract = relationship("Contract", back_populates="invoices")

    @property
    def is_overdue(self):
        # bool() مقصودة: تعبير "and" يعيد المعامل الزائف نفسه، فكانت الخاصية
        # تعيد None (لا False) حين لا يوجد تاريخ استحقاق — فيظهر "None" في
        # تصدير CSV وتفشل أي مقارنة صارمة (is False).
        return bool(self.status != "Paid" and self.due_date
                    and self.due_date < date.today())


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
        """none | soon | overdue | unknown

        "unknown" = معدة لم يُسجَّل لها تاريخ فحص إطلاقًا.
        سابقًا كانت تُعامل كـ "سليم" فتختفي من التنبيهات تمامًا رغم أنها
        في الواقع لم تُفحص أبدًا — وهذا أخطر من التأخر في الفحص.
        """
        if not self.last_inspection_date:
            return "unknown"
        d = self.days_until_due
        if d is None:
            return "unknown"
        if d < 0:
            return "overdue"
        if d <= 30:
            return "soon"
        return "none"


class Contract(Base):
    """عقد صيانة سنوي لعميل (مع إمكانية ربطه بمشروع/موقع محدد)."""

    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True)
    contract_number = Column(String)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"))
    # اختياري: عقد خاص بموقع/مشروع بعينه بدل كل مواقع العميل
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"))
    title = Column(String)
    scope = Column(String)              # نطاق الصيانة: إنذار، رشاشات، شامل...
    start_date = Column(Date)
    end_date = Column(Date)
    value = Column(Float, default=0.0)  # القيمة السنوية
    payment_cycle = Column(String, default="سنوي")   # سنوي، نصف سنوي، ربعي، شهري
    visits_per_year = Column(Integer, default=4)
    status = Column(String, default="Active")        # Active, Suspended, Cancelled
    notes = Column(Text)

    client = relationship("Client", back_populates="contracts")
    project = relationship("Project", back_populates="contracts")
    visits = relationship(
        "ContractVisit", back_populates="contract",
        cascade="all, delete-orphan", order_by="ContractVisit.visit_date"
    )
    invoices = relationship("Invoice", back_populates="contract", passive_deletes=True)

    # ---------------- خصائص محسوبة ----------------

    @property
    def client_name(self):
        return self.client.name if self.client else ""

    @property
    def project_name(self):
        return self.project.name if self.project else ""

    @property
    def days_remaining(self):
        """الأيام المتبقية حتى انتهاء العقد (سالبة = منتهٍ)."""
        if not self.end_date:
            return None
        return (self.end_date - date.today()).days

    @property
    def alert_level(self):
        """none | soon | expired | unknown — لتلوين حالة السريان.

        soon = ينتهي خلال 60 يومًا (وقت كافٍ لبدء إجراءات التجديد).
        """
        # عقد ملغى/موقوف: لا معنى لحساب السريان الزمني له، ويجب ألا يظهر
        # كـ "ساري" في خانة السريان — نميّزه بمستوى مستقل.
        if self.status in ("Cancelled", "Suspended"):
            return "inactive"
        if not self.end_date:
            return "unknown"
        d = self.days_remaining
        if d < 0:
            return "expired"
        if d <= 60:
            return "soon"
        return "none"

    @property
    def is_active(self):
        """ساري فعليًا: الحالة Active والتاريخ ضمن المدة."""
        if self.status != "Active":
            return False
        today = date.today()
        if self.start_date and self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False
        return True

    @property
    def visits_done(self):
        return sum(1 for v in self.visits if v.status == "Done")

    @property
    def visits_remaining(self):
        """الزيارات المتبقية من الرصيد السنوي المتعاقد عليه."""
        return max(0, (self.visits_per_year or 0) - self.visits_done)

    @property
    def next_visit_date(self):
        """أقرب زيارة مجدولة لم تُنفَّذ بعد."""
        pending = [v.visit_date for v in self.visits
                   if v.status == "Scheduled" and v.visit_date]
        return min(pending) if pending else None

    @property
    def total_invoiced(self):
        return sum(i.amount or 0 for i in self.invoices)

    @property
    def total_unpaid(self):
        return sum(i.amount or 0 for i in self.invoices if i.status != "Paid")


class ContractVisit(Base):
    """زيارة صيانة ضمن عقد."""

    __tablename__ = "contract_visits"

    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"),
                         nullable=False)
    visit_date = Column(Date)
    status = Column(String, default="Scheduled")  # Scheduled, Done, Missed
    technician = Column(String)
    findings = Column(Text)     # ما لوحظ أثناء الزيارة
    notes = Column(Text)

    contract = relationship("Contract", back_populates="visits")

    @property
    def is_overdue(self):
        """زيارة مجدولة فات موعدها ولم تُنفَّذ."""
        return bool(self.status == "Scheduled" and self.visit_date
                    and self.visit_date < date.today())


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
    _migrate_add_columns()


def _migrate_add_columns():
    """
    ترحيل تدريجي للأعمدة المضافة على جداول موجودة مسبقًا.

    create_all() ينشئ الجداول الناقصة فقط، ولا يضيف عمودًا جديدًا إلى جدول
    قائم. قاعدة بيانات المستخدم الحالية فيها جدول invoices بلا عمود
    contract_id، فبدون هذا الترحيل يفشل أي استعلام على الفواتير بخطأ
    "no such column: invoices.contract_id".
    """
    from sqlalchemy import text as _text

    # (اسم الجدول، اسم العمود، تعريفه في SQLite)
    wanted = [
        ("invoices", "contract_id", "INTEGER REFERENCES contracts(id)"),
    ]

    with engine.begin() as conn:
        for table, column, ddl in wanted:
            try:
                cols = [r[1] for r in conn.execute(_text(f"PRAGMA table_info({table})"))]
            except Exception:
                continue
            if not cols or column in cols:
                continue
            try:
                conn.execute(_text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                print(f"تم تحديث بنية الجدول {table}: أضيف العمود {column}")
            except Exception as e:
                print(f"تعذر إضافة العمود {column} إلى {table}:", e)


def get_session():
    return SessionLocal()


# ---------------------------------------------------------------------------
# Shared query helpers
# ---------------------------------------------------------------------------

def _escape_like(text):
    """
    يهرّب محارف LIKE الخاصة (% و _) حتى لا يتحول بحث المستخدم عن "%" أو "_"
    إلى بحث شامل يعيد كل السجلات.
    """
    return (text.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_"))


def search_projects(session, text="", status="", client_id=None):
    q = session.query(Project)
    if text:
        like = f"%{_escape_like(text)}%"
        q = q.filter(or_(
            Project.name.ilike(like, escape="\\"),
            Project.site.ilike(like, escape="\\"),
            Project.building.ilike(like, escape="\\"),
            Project.scope.ilike(like, escape="\\"),
            Project.standard.ilike(like, escape="\\"),
            Project.status.ilike(like, escape="\\"),
            Project.notes.ilike(like, escape="\\"),
        ))
    if status:
        q = q.filter(Project.status == status)
    if client_id:
        q = q.filter(Project.client_id == client_id)
    return q.order_by(Project.id.desc()).all()


def upcoming_inspections(session, within_days=30):
    """
    المعدات التي يلزم الانتباه لها: متأخرة، أو قريبة الاستحقاق،
    أو لم يُسجَّل لها تاريخ فحص إطلاقًا ("unknown").

    سابقًا كانت المعدات بلا تاريخ فحص تُستثنى من هذه القائمة رغم أنها
    الأولى بالمتابعة.
    """
    items = session.query(Equipment).all()
    out = [e for e in items if e.alert_level in ("soon", "overdue", "unknown")]

    def sort_key(e):
        # المتأخر أولًا، ثم غير المفحوص، ثم الأقرب موعدًا
        rank = {"overdue": 0, "unknown": 1, "soon": 2}.get(e.alert_level, 3)
        d = e.days_until_due
        return (rank, d if d is not None else 10**6)

    out.sort(key=sort_key)
    return out


def unpaid_invoices(session):
    return session.query(Invoice).filter(Invoice.status != "Paid").order_by(Invoice.due_date.asc()).all()


def search_contracts(session, text="", status="", client_id=None, only_expiring=False):
    """بحث/فلترة العقود. only_expiring = المنتهية أو التي تنتهي خلال 60 يومًا."""
    q = session.query(Contract)
    if text:
        pattern = f"%{_escape_like(text)}%"
        q = q.filter(or_(
            Contract.title.ilike(pattern, escape="\\"),
            Contract.contract_number.ilike(pattern, escape="\\"),
            Contract.scope.ilike(pattern, escape="\\"),
        ))
    if status:
        q = q.filter(Contract.status == status)
    if client_id:
        q = q.filter(Contract.client_id == client_id)

    items = q.order_by(Contract.id.desc()).all()
    if only_expiring:
        items = [c for c in items if c.alert_level in ("expired", "soon")]
    return items


def expiring_contracts(session, within_days=60):
    """العقود المنتهية أو التي توشك على الانتهاء — للتنبيه في لوحة المعلومات."""
    items = session.query(Contract).filter(Contract.status == "Active").all()
    out = [c for c in items if c.alert_level in ("expired", "soon", "unknown")]

    def sort_key(c):
        rank = {"expired": 0, "unknown": 1, "soon": 2}.get(c.alert_level, 3)
        d = c.days_remaining
        return (rank, d if d is not None else 10**6)

    out.sort(key=sort_key)
    return out


def due_contract_visits(session, within_days=30):
    """زيارات الصيانة المتأخرة أو المستحقة خلال المدة المحددة."""
    from datetime import date as _date
    limit = _date.today() + timedelta(days=within_days)
    return (session.query(ContractVisit)
            .filter(ContractVisit.status == "Scheduled")
            .filter(ContractVisit.visit_date != None)  # noqa: E711
            .filter(ContractVisit.visit_date <= limit)
            .order_by(ContractVisit.visit_date.asc())
            .all())


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

    contracts = session.query(Contract).all()
    active_contracts = [c for c in contracts if c.is_active]
    contract_alerts = expiring_contracts(session)

    return {
        "total_contracts": len(contracts),
        "active_contracts": len(active_contracts),
        "contracts_value": sum(c.value or 0 for c in active_contracts),
        "contract_alerts": contract_alerts,
        "due_visits": due_contract_visits(session),
        "total_projects": len(projects),
        "status_counts": status_counts,
        "total_clients": session.query(Client).count(),
        "total_invoiced": total_invoiced,
        "total_unpaid": total_unpaid,
        "overdue_invoices": overdue_count,
        "equipment_alerts": equip_alerts,
    }
