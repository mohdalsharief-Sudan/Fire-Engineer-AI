"""
المعدات_tab.py
───────────────
وحدة عرض معدات الحريق من المكتبة المركزية (PostgreSQL).
تُضاف إلى FireEngineerAI كـ تبويب جديد.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QComboBox, QLineEdit, QMessageBox, QScrollArea,
    QFrame, QHeaderView, QAbstractItemView, QDoubleSpinBox, QSpinBox,
    QToolButton, QMenu, QSplitter, QGroupBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from sqlalchemy import or_
from library_db import (
    get_library_session, LibraryEquipment, LibraryCategory, LibraryManufacturer
)
from applog import get_logger

logger = get_logger(__name__)

# نماذج للاستعلام من PostgreSQL (من جداول fire_equipment)
# لمهندس: هذه تعمل على جداول معدات الحريق في PostgreSQL
# (ليست fea_equipment الخاصة بـ FireEngineerAI)


class EquipmentTab(QWidget):
    """
    تبويب عرض معدات الحريق중앙 library.
    يظهر جميع المعدات من PostgreSQL مع قدراسة البحث والتصنيف.
    """

    equipment_selected = Signal(object)  # إشارة عند اختيار معدة

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session = None
        self.all_equipment = []
        self.filtered_equipment = []
        self._stats_cache = {}
        self.selected_category_id = None
        self.selected_manufacturer_id = None
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        """بناء واجهة التبويب"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # ── شريط البحث والتصنيف ──
        filter_frame = QFrame()
        filter_frame.setObjectName("FilterFrame")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setSpacing(10)
        filter_layout.setContentsMargins(10, 10, 10, 10)

        # بحث نصي
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 بحث عن اسم أو كود المعدة...")
        self.search_edit.textChanged.connect(self._debounce_search)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)
        filter_layout.addWidget(self.search_edit)

        # فئة
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("كل الفئات")
        self.cat_combo.currentTextChanged.connect(self._debounce_filter)
        filter_layout.addWidget(self.cat_combo)

        # مصنّع
        self.mfr_combo = QComboBox()
        self.mfr_combo.addItem("كل المصنّعين")
        self.mfr_combo.currentTextChanged.connect(self._debounce_filter)
        filter_layout.addWidget(self.mfr_combo)

        # زر تحديث
        refresh_btn = QPushButton("🔄 تحديث")
        refresh_btn.clicked.connect(self.load_data)
        filter_layout.addWidget(refresh_btn)

        main_layout.addWidget(filter_frame)

        # ── جدول المعدات ──
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "الكود", "الموديل / الاسم", "الفئة", "المصنّع",
            "س.الشراء", "س.التركيب", "س.البيعية", "الربح %"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a2e;
                alternate-background-color: #252540;
                gridline-color: #333355;
                font-size: 13px;
            }
            QTableWidget::item:selected {
                background-color: #3498DB;
                color: white;
            }
            QHeaderView::section {
                background-color: #0f1626;
                color: #3498DB;
                padding: 8px;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid #3498DB;
            }
        """)
        self.table.itemClicked.connect(self.on_equipment_click)
        main_layout.addWidget(self.table)

        # ── شريط الإحصائيات ──
        stats_frame = QFrame()
        stats_frame.setObjectName("StatsFrame")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setSpacing(15)

        self.lbl_total = QLabel("0 معدة")
        self.lbl_total.setObjectName("StatLabel")
        stats_layout.addWidget(self.lbl_total)

        self.lbl_categories = QLabel("0 فئة")
        self.lbl_categories.setObjectName("StatLabel")
        stats_layout.addWidget(self.lbl_categories)

        self.lbl_manufacturers = QLabel("0 مصنّع")
        self.lbl_manufacturers.setObjectName("StatLabel")
        stats_layout.addWidget(self.lbl_manufacturers)

        self.lbl_with_prices = QLabel("0 بسعر")
        self.lbl_with_prices.setObjectName("StatLabel")
        stats_layout.addWidget(self.lbl_with_prices)

        main_layout.addWidget(stats_frame)

        self.setLayout(main_layout)

    def load_data(self):
        """تحميل جميع المعدات من PostgreSQL"""
        try:
            self.session = get_library_session()
            # استعلام المعدات مع الانضمام للفئات والمصنّعين
            from sqlalchemy import desc
            query = self.session.query(LibraryEquipment).outerjoin(
                LibraryCategory, LibraryEquipment.category_id == LibraryCategory.id
            ).outerjoin(
                LibraryManufacturer, LibraryEquipment.manufacturer_id == LibraryManufacturer.id
            ).order_by(
                LibraryCategory.sort_order, LibraryEquipment.type_ar
            )
            self.all_equipment = query.all()

            # تحميل العلاقات مسبقًا لتجنب الاستعلامات الكسولة لاحقًا
            for eq in self.all_equipment:
                if eq.category is not None:
                    eq.category_name = eq.category.name
                if eq.manufacturer is not None:
                    eq.supplier_name = eq.manufacturer.name

            # تعبئة قوائم الفئات والمصنّعين للتصفية
            self._categories = self.session.query(LibraryCategory)\
                .filter(LibraryCategory.is_active == 1)\
                .order_by(LibraryCategory.sort_order, LibraryCategory.name).all()
            self._manufacturers = self.session.query(LibraryManufacturer)\
                .filter(LibraryManufacturer.is_active == 1)\
                .order_by(LibraryManufacturer.name).all()
            
            # إحصائيات عامة一次性
            self._stats_cache = {
                'cat_count': self.session.query(LibraryCategory).count(),
                'mfr_count': self.session.query(LibraryManufacturer).count(),
                'priced_count': self.session.query(LibraryEquipment)\
                    .filter(LibraryEquipment.supply_price_sar > 0).count(),
            }
            
            self.apply_filters()
            logger.info(f"✅ تحميل {len(self.all_equipment)} معدة منPostgreSQL")
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل المعدات: {e}")
            QMessageBox.warning(self, "خطأ", f"تعذّر تحميل المعدات:\n{e}")
        # لا نغلق الجلسة — نحتفظ بها لحياة الخطوة

    def apply_filters(self):
        """تطبيق الفلاتر الحالية"""
        search = self.search_edit.text().strip().lower()
        cat_name = self.cat_combo.currentText()
        mfr_name = self.mfr_combo.currentText()

        filtered = []
        for eq in self.all_equipment:
            # بحث نصي
            if search:
                eq_code = (eq.code or "").lower()
                eq_model = (eq.model or "").lower()
                eq_model_ar = (eq.model_ar or "").lower()
                eq_supplier = (eq.supplier_name or "").lower()
                if not any(search in s for s in [eq_code, eq_model, eq_model_ar, eq_supplier]):
                    continue

            # فلترة الفئة
            if cat_name and cat_name != "كل الفئات":
                cat_name_eq = getattr(eq, 'category_name', '') or ''
                if not cat_name_eq or cat_name_eq != cat_name:
                    continue

            # فلترة المصنّع
            if mfr_name and mfr_name != "كل المصنّعين":
                if (getattr(eq, 'supplier_name', '') or '') != mfr_name:
                    continue

            filtered.append(eq)

        self.filtered_equipment = filtered
        self.refresh_table()
        self.update_stats()

    def refresh_table(self):
        """تحديث الجدول — يبنى الصفوف فقط عند التغيير، وينfone الأعمدة مرة واحدة"""
        try:
            new_count = len(self.filtered_equipment)
            old_count = self.table.rowCount()
            if new_count != old_count:
                self.table.setRowCount(new_count)

            for i, eq in enumerate(self.filtered_equipment):
                self.table.setItem(i, 0, QTableWidgetItem(eq.code or ""))
                name = (getattr(eq, 'model_ar', None) or getattr(eq, 'model', None) or '') or eq.code or ''
                self.table.setItem(i, 1, QTableWidgetItem(name))
                cat_name = (getattr(eq, 'category_name', None) or (eq.category.name if eq.category else None) or '') or ''
                self.table.setItem(i, 2, QTableWidgetItem(cat_name))
                mfr_name = (getattr(eq, 'supplier_name', None) or (eq.manufacturer.name if eq.manufacturer else None) or '') or ''
                self.table.setItem(i, 3, QTableWidgetItem(mfr_name))
                supply = eq.supply_price_sar or 0
                install = eq.install_price_sar or 0
                selling = eq.selling_price_sar or 0
                profit = eq.profit_percent or 0
                self.table.setItem(i, 4, QTableWidgetItem(f"{supply:,.0f}"))
                self.table.setItem(i, 5, QTableWidgetItem(f"{install:,.0f}"))
                self.table.setItem(i, 6, QTableWidgetItem(f"{selling:,.0f}"))
                self.table.setItem(i, 7, QTableWidgetItem(f"{profit}%"))

            if new_count != old_count:
                self.table.resizeColumnsToContents()
        except RuntimeError:
            pass  #widget تمحذف بعد التبديل بين التبويبات

    def _get_item_color(self, eq):
        """إرجاع اللون المناسب حسب حالة المعدة"""
        # محاولة للحصول على مظهر احترافي
        return None  # سنعتمد على تنسيق الجدول

    def _debounce_search(self):
        """تأخير البحث 300ms لتجنب التفعيل المتكرر"""
        self._search_timer.start(300)

    def _debounce_filter(self):
        """تأخير الفلاتر 200ms لتجنب التفعيل المتكرر"""
        self._search_timer.start(200)

    def _do_search(self):
        """تنفيذ البحث بعد انتهاء المهلة"""
        self.apply_filters()

    def filter_equipment(self, text=None):
        """استدعاء تلقائي عند تغيير الفلاتر"""
        self.apply_filters()

    def update_stats(self):
        """تحديث إحصائيات العدادات — تستخدم المخزن الموجود"""
        total = len(self.filtered_equipment)
        self.lbl_total.setText(f"{total:,} معدة")
        self.lbl_categories.setText(f"{self._stats_cache.get('cat_count', 0):,} فئة")
        self.lbl_manufacturers.setText(f"{self._stats_cache.get('mfr_count', 0):,} مصنّع")
        self.lbl_with_prices.setText(f"{self._stats_cache.get('priced_count', 0):,} بسعر")

    def on_equipment_click(self, item):
        """عند النقر على معدة - إشعال الإشارة"""
        row = item.row()
        if row < len(self.filtered_equipment):
            eq = self.filtered_equipment[row]
            self.equipment_selected.emit(eq)
            return eq
        return None

    def get_equipment_by_code(self, code):
        """بحث عن معدة بالكود"""
        if not self.session:
            self.session = get_library_session()
        try:
            return self.session.query(LibraryEquipment).filter(
                LibraryEquipment.code == code
            ).first()
        except Exception:
            return None

    def get_equipment_details(self, equipment_id):
        """الحصول على تفاصيل معدة كاملة"""
        if not self.session:
            self.session = get_library_session()
        try:
            return self.session.query(LibraryEquipment).filter(
                LibraryEquipment.id == equipment_id
            ).first()
        except Exception:
            return None


# نماذج مساعدة للاستعلام (ملخص من PostgreSQL)


# ······························································
# ملاحظة: هذه النماذج تُستخدم للقراءة فقط من PostgreSQL
# وهي تختلف عن نماذج FireEngineerAI الداخلية (fea_*)
# ······························································