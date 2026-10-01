"""
library_db.py
─────────────
وحدة الاتصال بقاعدة معدات الحريق المركزية (PostgreSQL).
تُستخدم للقراءة من جداول fire_equipment المشتركة.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import os

# اتصال بقاعدة المعدات المشتركة
PG_USER = os.environ.get("PG_USER", "postgres")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "Msh20041970")
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = os.environ.get("PG_PORT", "5432")
PG_DB = os.environ.get("PG_DB", "fire_equipment")

LIBRARY_DB_URL = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# محرك منفصل للمكتبة المركزية
library_engine = create_engine(LIBRARY_DB_URL, echo=False, future=True)
LibraryBase = declarative_base()
library_session_factory = sessionmaker(bind=library_engine)


# ────────────────────────────────────────
# النماذج (تطابق جداول fire_equipment في PostgreSQL)
# ────────────────────────────────────────

class LibraryCategory(LibraryBase):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    code = Column(String)
    name = Column(String)
    name_ar = Column(String)
    parent_id = Column(Integer)
    level = Column(Integer)
    sort_order = Column(Integer)
    description = Column(Text)

    def __repr__(self):
        return f"<Category {self.name_ar or self.name}>"


class LibraryManufacturer(LibraryBase):
    __tablename__ = "manufacturers"

    id = Column(Integer, primary_key=True)
    code = Column(String)
    name = Column(String)
    name_ar = Column(String)
    country = Column(String)
    website = Column(String)
    notes = Column(Text)

    def __repr__(self):
        return f"<Manufacturer {self.name}>"


class LibraryEquipment(LibraryBase):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False)
    name = Column(String)
    category_id = Column(Integer)
    manufacturer_id = Column(Integer)

    model = Column(String)
    model_ar = Column(String)
    type = Column(String)
    type_ar = Column(String)

    specifications = Column(Text)
    specifications_ar = Column(Text)
    description = Column(Text)
    description_ar = Column(Text)
    certifications = Column(Text)
    applications = Column(Text)
    conditions = Column(Text)

    supply_price_sar = Column(Float, default=0)
    install_price_sar = Column(Float, default=0)
    accessories_price_sar = Column(Float, default=0)
    selling_price_sar = Column(Float, default=0)

    profit_percent = Column(Float, default=25)
    price_type = Column(String)
    currency = Column(String, default="SAR")
    price_note = Column(Text)
    supplier_name = Column(String)
    price_sar = Column(Float, default=0)

    is_active = Column(Integer, default=1)
    is_certified = Column(Integer, default=0)

    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    # علاقات (للاستخدام المريح)
    category = None  # سيتم تعبئتها يدويًا عند الاستعلام
    manufacturer = None

    def __repr__(self):
        return f"<Equipment {self.code}>"


# Helper function للحصول على session للمكتبة المركزية
def get_library_session():
    """فتح جلسة لقاعدة المعدات المركزية"""
    return library_session_factory()


# إنشاء جميع الجداول إذا لم تكن موجودة (لأغراض الضمان)
# (في الواقع الجداول موجودة بالفعل من عملية النقل، لكن هذا يضمن الاتصال)
try:
    LibraryBase.metadata.create_all(library_engine)
    print("✅ اتصال مكتبة المعدات المركزية (PostgreSQL) ناجح")
except Exception as e:
    print(f"⚠️ تحذير: {e}")
