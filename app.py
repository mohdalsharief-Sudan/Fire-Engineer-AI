"""
app.py
تطبيق إدارة مشاريع الحماية من الحريق — واجهة احترافية بثيم داكن.

يتطلب:
    pip install PySide6 sqlalchemy reportlab
    (اختياري لدعم عربي أفضل في PDF: pip install arabic-reshaper python-bidi)

التشغيل:
    python app.py
"""

import os
import shutil
import sys
from datetime import date

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFormLayout, QLineEdit,
    QComboBox, QTextEdit, QPushButton, QDateEdit, QFileDialog,
    QHBoxLayout, QVBoxLayout, QGridLayout, QTableWidget, QTableWidgetItem,
    QLabel, QStackedWidget, QMessageBox, QAbstractItemView, QListWidget,
    QListWidgetItem, QDoubleSpinBox, QSpinBox, QScrollArea, QFrame,
    QSizePolicy, QButtonGroup, QHeaderView, QPlainTextEdit
)
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtCore import Qt, QDate, QUrl
from sqlalchemy import or_

from database import (
    init_db, get_session, Project, Client, Invoice, Equipment,
    search_projects, upcoming_inspections, unpaid_invoices, dashboard_stats,
    ATTACHMENTS_DIR, REPORTS_DIR, BACKUPS_DIR, DB_PATH,
)
from theme import QSS, STATUS_COLORS, status_badge_style, alert_badge_style
from settings import load_settings, save_settings, save_logo, clear_logo
import reports as reports_module

APP_TITLE = "FireEngineerAI — نظام إدارة مشاريع الحماية من الحريق"

# مصدر واحد لحالات المشروع (كانت مكرّرة في أكثر من موضع)
PROJECT_STATUSES = ["Design", "Supply", "Install", "Testing", "Handover"]

NAV_ITEMS = [
    ("dashboard", "لوحة المعلومات"),
    ("projects", "المشاريع"),
    ("clients", "العملاء"),
    ("equipment", "المعدات والفحص"),
    ("invoices", "الفواتير"),
    ("reports", "التقارير"),
    ("settings", "الإعدادات"),
]


def to_qdate(d):
    if d:
        return QDate(d.year, d.month, d.day)
    return QDate.currentDate()


def make_card(title=None):
    """بطاقة بسيطة بخلفية Surface وحدود مدورة."""
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    if title:
        lbl = QLabel(title)
        lbl.setObjectName("PageSubtitle")
        layout.addWidget(lbl)
    return card, layout


def set_badge_cell(table, row, col, text, style):
    """
    يضع شارة ملوّنة داخل خلية جدول بعرض كافٍ.

    المشكلة التي تعالجها: setCellWidget() وحده لا يُحسب ضمن عرض العمود عند
    ResizeToContents (لأن الحساب يعتمد على عناصر QTableWidgetItem لا الودجات)،
    فكانت الشارات تظهر مقصوصة مثل "غير مة" بدل "غير مسددة".
    الحل: نضع عنصرًا نصيًا مخفيًا خلف الشارة ليأخذ العمود عرضه الصحيح.
    """
    label = QLabel(text)
    label.setStyleSheet(style)
    label.setAlignment(Qt.AlignCenter)
    fm = label.fontMetrics()
    # عرض النص + مساحة الحشو (padding 10px من الجانبين) + الإطار + هامش أمان
    badge_w = fm.horizontalAdvance(text) + 44
    label.setMinimumWidth(badge_w)
    label.setMinimumHeight(fm.height() + 6)

    # عنصر مخفي يمنح العمود عرضًا كافيًا عند ResizeToContents
    sizing_item = QTableWidgetItem(text + "      ")
    sizing_item.setForeground(Qt.transparent)
    table.setItem(row, col, sizing_item)

    holder = QWidget()
    lay = QHBoxLayout(holder)
    lay.setContentsMargins(6, 3, 6, 3)
    lay.addWidget(label)
    table.setCellWidget(row, col, holder)


def tune_table(table, stretch_col=None):
    """
    إعدادات موحّدة لجداول البرنامج: عرض أعمدة مناسب، إخفاء عمود الترقيم
    الرأسي الفارغ، وارتفاع صفوف مريح.
    بدونها كانت الأعمدة ضيقة والنصوص العربية مقصوصة بنقاط (...).
    """
    table.verticalHeader().setVisible(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    if stretch_col is not None:
        header.setSectionResizeMode(stretch_col, QHeaderView.Stretch)
    else:
        header.setStretchLastSection(True)
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    # ارتفاع صف كافٍ لاحتواء الشارات الملوّنة دون قصّها عموديًا
    table.verticalHeader().setDefaultSectionSize(38)
    return table


def make_stat_card(value_text, label_text):
    card, layout = make_card()
    val = QLabel(value_text)
    val.setObjectName("StatValue")
    lbl = QLabel(label_text)
    lbl.setObjectName("StatLabel")
    layout.addWidget(val)
    layout.addWidget(lbl)
    card.value_label = val
    return card


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(_app_icon())
        self.setMinimumSize(1360, 860)
        self.setLayoutDirection(Qt.RightToLeft)

        self.session = get_session()

        # حالات التتبع للنماذج الحالية
        self.current_edit_project_id = None
        self.current_viewed_project_id = None
        self.current_edit_client_id = None
        self.current_edit_equipment_id = None
        self.current_edit_invoice_id = None

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        root.addWidget(self.build_sidebar())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(24, 20, 24, 20)

        self.pages = QStackedWidget()
        right_layout.addWidget(self.pages)
        root.addWidget(right, 1)

        self.page_dashboard = self.build_dashboard_page()
        self.page_projects = self.build_projects_page()
        self.page_project_form = self.build_project_form_page()
        self.page_project_details = self.build_project_details_page()
        self.page_clients = self.build_clients_page()
        self.page_equipment = self.build_equipment_page()
        self.page_invoices = self.build_invoices_page()
        self.page_reports = self.build_reports_page()
        self.page_settings = self.build_settings_page()

        for p in [
            self.page_dashboard, self.page_projects, self.page_project_form,
            self.page_project_details, self.page_clients, self.page_equipment,
            self.page_invoices, self.page_reports, self.page_settings
        ]:
            self.pages.addWidget(p)

        self.statusBar().showMessage("جاهز")

        self.refresh_all()
        self.show_dashboard()

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    def build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(230)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("🔥 FireEngineerAI")
        title.setObjectName("SidebarTitle")
        subtitle = QLabel("إدارة مشاريع الحماية من الحريق")
        subtitle.setObjectName("SidebarSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}

        nav_actions = {
            "dashboard": self.show_dashboard,
            "projects": self.show_projects,
            "clients": self.show_clients,
            "equipment": self.show_equipment,
            "invoices": self.show_invoices,
            "reports": self.show_reports,
            "settings": self.show_settings,
        }

        for key, label in NAV_ITEMS:
            btn = QPushButton(f"  {label}")
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(nav_actions[key])
            layout.addWidget(btn)
            self.nav_group.addButton(btn)
            self.nav_buttons[key] = btn

        layout.addStretch()

        add_project_btn = QPushButton("+ مشروع جديد")
        add_project_btn.setObjectName("PrimaryButton")
        add_project_btn.setCursor(Qt.PointingHandCursor)
        add_project_btn.clicked.connect(self.new_project_form)
        layout.addWidget(add_project_btn)

        backup_btn = QPushButton("نسخ احتياطي الآن")
        backup_btn.setCursor(Qt.PointingHandCursor)
        backup_btn.clicked.connect(self.backup_database)
        layout.addWidget(backup_btn)
        layout.setContentsMargins(0, 0, 0, 16)

        return sidebar

    def set_active_nav(self, key):
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)

    def page_header(self, layout, title, subtitle=""):
        row = QVBoxLayout()
        t = QLabel(title)
        t.setObjectName("PageTitle")
        row.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("PageSubtitle")
            row.addWidget(s)
        layout.addLayout(row)

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def build_dashboard_page(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.page_header(layout, "لوحة المعلومات", "نظرة عامة سريعة على المشاريع والفواتير والمعدات")

        stats_row = QHBoxLayout()
        self.stat_projects = make_stat_card("0", "إجمالي المشاريع")
        self.stat_clients = make_stat_card("0", "العملاء")
        self.stat_unpaid = make_stat_card("0.00", "فواتير غير مسددة")
        self.stat_alerts = make_stat_card("0", "تنبيهات فحص المعدات")
        for c in [self.stat_projects, self.stat_clients, self.stat_unpaid, self.stat_alerts]:
            stats_row.addWidget(c)
        layout.addLayout(stats_row)

        mid_row = QHBoxLayout()

        # حالة المشاريع
        status_card, status_layout = make_card("توزيع المشاريع حسب الحالة")
        self.status_breakdown_layout = QVBoxLayout()
        status_layout.addLayout(self.status_breakdown_layout)
        mid_row.addWidget(status_card, 1)

        # تنبيهات الفحص
        alerts_card, alerts_layout = make_card("مواعيد فحص قريبة أو متأخرة")
        self.dashboard_alerts_table = QTableWidget(0, 4)
        self.dashboard_alerts_table.setHorizontalHeaderLabels(["المعدة", "المشروع", "الفحص القادم", "الحالة"])
        self.dashboard_alerts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.dashboard_alerts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dashboard_alerts_table.setMaximumHeight(220)
        tune_table(self.dashboard_alerts_table, stretch_col=1)
        alerts_layout.addWidget(self.dashboard_alerts_table)
        mid_row.addWidget(alerts_card, 2)

        layout.addLayout(mid_row)

        # فواتير غير مسددة
        inv_card, inv_layout = make_card("فواتير غير مسددة / متأخرة")
        self.dashboard_invoices_table = QTableWidget(0, 5)
        self.dashboard_invoices_table.setHorizontalHeaderLabels(
            ["رقم الفاتورة", "المشروع", "المبلغ", "الاستحقاق", "الحالة"]
        )
        self.dashboard_invoices_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.dashboard_invoices_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        tune_table(self.dashboard_invoices_table, stretch_col=1)
        inv_layout.addWidget(self.dashboard_invoices_table)
        layout.addWidget(inv_card)

        return w

    def refresh_dashboard(self):
        stats = dashboard_stats(self.session)

        self.stat_projects.value_label.setText(str(stats["total_projects"]))
        self.stat_clients.value_label.setText(str(stats["total_clients"]))
        self.stat_unpaid.value_label.setText(f"{stats['total_unpaid']:,.2f}")
        self.stat_alerts.value_label.setText(str(len(stats["equipment_alerts"])))

        # امسح توزيع الحالات القديم
        while self.status_breakdown_layout.count():
            item = self.status_breakdown_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total = max(stats["total_projects"], 1)
        for status, count in stats["status_counts"].items():
            row = QHBoxLayout()
            badge = QLabel(status)
            badge.setStyleSheet(status_badge_style(status))
            count_lbl = QLabel(f"{count} ({count * 100 // total}%)")
            count_lbl.setObjectName("PageSubtitle")
            row.addWidget(badge)
            row.addStretch()
            row.addWidget(count_lbl)
            wrap = QWidget()
            wrap.setLayout(row)
            self.status_breakdown_layout.addWidget(wrap)
        self.status_breakdown_layout.addStretch()

        # تنبيهات الفحص
        alerts = stats["equipment_alerts"]
        self.dashboard_alerts_table.setRowCount(0)
        for e in alerts[:15]:
            row = self.dashboard_alerts_table.rowCount()
            self.dashboard_alerts_table.insertRow(row)
            self.dashboard_alerts_table.setItem(row, 0, QTableWidgetItem(e.name or ""))
            self.dashboard_alerts_table.setItem(row, 1, QTableWidgetItem(e.project.name if e.project else ""))
            nxt = e.next_inspection_date
            self.dashboard_alerts_table.setItem(row, 2, QTableWidgetItem(str(nxt) if nxt else "-"))
            _txt = {"overdue": "متأخر", "soon": "قريب",
                    "unknown": "لم يُفحص"}.get(e.alert_level, "قريب")
            set_badge_cell(self.dashboard_alerts_table, row, 3, _txt,
                           alert_badge_style(e.alert_level))

        # فواتير غير مسددة
        invs = unpaid_invoices(self.session)
        self.dashboard_invoices_table.setRowCount(0)
        for i in invs[:15]:
            row = self.dashboard_invoices_table.rowCount()
            self.dashboard_invoices_table.insertRow(row)
            self.dashboard_invoices_table.setItem(row, 0, QTableWidgetItem(i.invoice_number or f"#{i.id}"))
            self.dashboard_invoices_table.setItem(row, 1, QTableWidgetItem(i.project.name if i.project else ""))
            self.dashboard_invoices_table.setItem(row, 2, QTableWidgetItem(f"{i.amount:,.2f}" if i.amount else "0.00"))
            self.dashboard_invoices_table.setItem(row, 3, QTableWidgetItem(str(i.due_date) if i.due_date else "-"))
            # كان يعرض حالة إنجليزية خام ("Unpaid") وسط واجهة عربية،
            # وبلون أخضر يوحي بأنها مسددة.
            if i.is_overdue:
                set_badge_cell(self.dashboard_invoices_table, row, 4,
                               "متأخرة", alert_badge_style("overdue"))
            else:
                _txt = "مسددة" if i.status == "Paid" else "غير مسددة"
                _lvl = "none" if i.status == "Paid" else "soon"
                set_badge_cell(self.dashboard_invoices_table, row, 4, _txt,
                               alert_badge_style(_lvl))

    # ------------------------------------------------------------------
    # Navigation show_* helpers (نتابع في الأجزاء التالية)
    # ------------------------------------------------------------------
    def show_dashboard(self):
        self.set_active_nav("dashboard")
        self.refresh_dashboard()
        self.pages.setCurrentWidget(self.page_dashboard)
        self.statusBar().showMessage("لوحة المعلومات")

    def refresh_all(self):
        self.refresh_dashboard()
        self.refresh_projects_table()
        self.refresh_clients_table()
        self.refresh_equipment_table()
        self.refresh_invoices_table()
        self.reload_client_combo()
        self.reload_project_combos()

    def backup_database(self):
        try:
            ts = date.today().isoformat()
            dest = os.path.join(BACKUPS_DIR, f"db_backup_{ts}.sqlite3")
            shutil.copy2(DB_PATH, dest)
            QMessageBox.information(self, "نسخ احتياطي", f"تم إنشاء نسخة احتياطية:\n{dest}")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر إنشاء نسخة احتياطية:\n{e}")

    def safe_commit(self, action="الحفظ"):
        """
        يحفظ التغييرات ويتعامل مع الأخطاء بأمان.

        سبب وجودها: في SQLAlchemy إذا فشل commit (مثلًا قيمة مطلوبة ناقصة)
        تبقى الجلسة في حالة معطوبة، وكل عملية حفظ لاحقة تفشل بـ
        PendingRollbackError حتى لو كانت سليمة تمامًا — أي أن البرنامج
        يتوقف عن الحفظ نهائيًا حتى يُعاد تشغيله. rollback() يعيد الجلسة
        لحالة صالحة.

        ترجع True عند النجاح و False عند الفشل.
        """
        try:
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(
                self, "خطأ في قاعدة البيانات",
                f"تعذر {action}. لم يتم حفظ أي تغيير.\n\nالتفاصيل:\n{e}"
            )
            return False

    # ------------------------------------------------------------------
    # Projects: قائمة + بحث
    # ------------------------------------------------------------------
    def build_projects_page(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        top_row = QHBoxLayout()
        self.page_header(top_row, "المشاريع", "")
        top_row.addStretch()
        new_btn = QPushButton("+ مشروع جديد")
        new_btn.setObjectName("PrimaryButton")
        new_btn.clicked.connect(self.new_project_form)
        top_row.addWidget(new_btn)
        layout.addLayout(top_row)

        filters = QHBoxLayout()
        self.project_search = QLineEdit()
        self.project_search.setPlaceholderText("ابحث بالاسم، الموقع، النطاق، الحالة...")
        self.project_search.textChanged.connect(self.refresh_projects_table)

        self.project_status_filter = QComboBox()
        # كان أول عنصر فارغًا تمامًا فيبدو كعطل. الآن له تسمية واضحة
        # مع الاحتفاظ بالقيمة الفارغة في الخلفية (userData) للفلترة.
        self.project_status_filter.addItem("كل الحالات", "")
        for _st in PROJECT_STATUSES:
            self.project_status_filter.addItem(_st, _st)
        self.project_status_filter.currentIndexChanged.connect(self.refresh_projects_table)

        self.project_client_filter = QComboBox()
        self.project_client_filter.addItem("كل العملاء", None)
        self.project_client_filter.currentIndexChanged.connect(self.refresh_projects_table)

        filters.addWidget(self.project_search, 3)
        filters.addWidget(self.project_status_filter, 1)
        filters.addWidget(self.project_client_filter, 1)
        layout.addLayout(filters)

        self.projects_table = QTableWidget(0, 7)
        self.projects_table.setHorizontalHeaderLabels(
            ["ID", "الاسم", "العميل", "الموقع", "النطاق", "الحالة", "المدة (أيام)"]
        )
        self.projects_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.projects_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.projects_table.itemDoubleClicked.connect(self.open_project_details_from_table)
        tune_table(self.projects_table, stretch_col=1)  # عمود الاسم يتمدد
        layout.addWidget(self.projects_table)

        return w

    def reload_client_combo(self):
        clients = self.session.query(Client).order_by(Client.name.asc()).all()
        combo = self.project_client_filter
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("كل العملاء", None)
        for c in clients:
            combo.addItem(c.name, c.id)
        idx = combo.findData(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

        # نموذج المشروع (إضافة/تعديل) أيضًا يحتاج قائمة عملاء
        if hasattr(self, "project_form_client_combo"):
            combo2 = self.project_form_client_combo
            current2 = combo2.currentData()
            combo2.blockSignals(True)
            combo2.clear()
            combo2.addItem("— بدون عميل —", None)
            for c in clients:
                combo2.addItem(c.name, c.id)
            idx2 = combo2.findData(current2)
            combo2.setCurrentIndex(idx2 if idx2 >= 0 else 0)
            combo2.blockSignals(False)

    def refresh_projects_table(self):
        text = self.project_search.text().strip()
        status = self.project_status_filter.currentData() or ""
        client_id = self.project_client_filter.currentData()
        rows = search_projects(self.session, text=text, status=status, client_id=client_id)
        self.fill_projects_table(self.projects_table, rows)

    def fill_projects_table(self, table, rows):
        table.setRowCount(0)
        for r in rows:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(r.id)))
            table.setItem(row, 1, QTableWidgetItem(r.name or ""))
            table.setItem(row, 2, QTableWidgetItem(r.client_name))
            table.setItem(row, 3, QTableWidgetItem(r.site or ""))
            table.setItem(row, 4, QTableWidgetItem(r.scope or ""))
            set_badge_cell(table, row, 5, r.status or "-",
                           status_badge_style(r.status or ""))
            days = ""
            if r.start_date and r.end_date:
                days = str((r.end_date - r.start_date).days)
            table.setItem(row, 6, QTableWidgetItem(days))

    def open_project_details_from_table(self, item):
        table = item.tableWidget()
        row = item.row()
        id_item = table.item(row, 0)
        if not id_item:
            return
        self.open_project_details(int(id_item.text()))

    # ------------------------------------------------------------------
    # Projects: نموذج إضافة / تعديل
    # ------------------------------------------------------------------
    def build_project_form_page(self):
        w = QWidget()
        outer = QVBoxLayout(w)

        self.project_form_title = QLabel("مشروع جديد")
        self.project_form_title.setObjectName("PageTitle")
        outer.addWidget(self.project_form_title)

        card, card_layout = make_card()
        form = QFormLayout()
        form.setSpacing(10)

        self.pf_name = QLineEdit()
        self.pf_client_combo = QComboBox()
        self.project_form_client_combo = self.pf_client_combo  # alias used by reload_client_combo
        self.pf_site = QLineEdit()
        self.pf_building = QLineEdit()

        self.pf_scope = QComboBox()
        self.pf_scope.addItems([
            "Fire Alarm", "Sprinklers", "Fire Pumps",
            "FM-200 / Clean Agent", "Wet Riser / Hose Reel",
            "Combined (Alarm + Sprinklers)", "Custom"
        ])

        self.pf_standard = QComboBox()
        self.pf_standard.addItems(["NFPA", "EN", "BS", "SBC", "Local AHJ", "Mixed"])

        self.pf_status = QComboBox()
        self.pf_status.addItems(PROJECT_STATUSES)

        self.pf_start = QDateEdit()
        self.pf_start.setCalendarPopup(True)
        self.pf_start.setDate(QDate.currentDate())

        self.pf_end = QDateEdit()
        self.pf_end.setCalendarPopup(True)
        self.pf_end.setDate(QDate.currentDate().addDays(30))

        self.pf_notes = QTextEdit()
        self.pf_notes.setPlaceholderText("ملاحظات، حدود العمل، متطلبات الدفاع المدني/AHJ...")
        self.pf_notes.setMaximumHeight(90)

        form.addRow("اسم المشروع *", self.pf_name)
        form.addRow("العميل", self.pf_client_combo)
        form.addRow("الموقع", self.pf_site)
        form.addRow("المبنى", self.pf_building)
        form.addRow("نطاق النظام", self.pf_scope)
        form.addRow("المعيار المرجعي", self.pf_standard)
        form.addRow("الحالة", self.pf_status)
        form.addRow("تاريخ البدء", self.pf_start)
        form.addRow("تاريخ الانتهاء", self.pf_end)
        form.addRow("ملاحظات", self.pf_notes)
        card_layout.addLayout(form)

        # مرفقات
        attach_row = QHBoxLayout()
        self.pf_attach_label = QLabel("لا توجد ملفات مرفقة")
        attach_btn = QPushButton("إضافة مرفقات")
        self.pf_pending_attachments = []

        def add_attachments():
            files, _ = QFileDialog.getOpenFileNames(
                self, "اختر المرفقات", "", "All Files (*);;PDF (*.pdf);;Images (*.png *.jpg *.jpeg);;CAD (*.dwg *.dxf)"
            )
            if files:
                self.pf_pending_attachments.extend(files)
                self.pf_attach_label.setText(f"{len(self.pf_pending_attachments)} ملف(ات) مضافة")

        attach_btn.clicked.connect(add_attachments)
        attach_row.addWidget(self.pf_attach_label)
        attach_row.addStretch()
        attach_row.addWidget(attach_btn)
        card_layout.addLayout(attach_row)

        outer.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.show_projects)
        self.pf_save_btn = QPushButton("حفظ المشروع")
        self.pf_save_btn.setObjectName("PrimaryButton")
        self.pf_save_btn.clicked.connect(self.save_project_form)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.pf_save_btn)
        outer.addLayout(btn_row)
        outer.addStretch()

        return w

    def new_project_form(self):
        self.current_edit_project_id = None
        self.project_form_title.setText("مشروع جديد")
        self.pf_save_btn.setText("حفظ المشروع")
        self.pf_name.clear()
        self.pf_client_combo.setCurrentIndex(0)
        self.pf_site.clear()
        self.pf_building.clear()
        self.pf_scope.setCurrentIndex(0)
        self.pf_standard.setCurrentIndex(0)
        self.pf_status.setCurrentIndex(0)
        self.pf_start.setDate(QDate.currentDate())
        self.pf_end.setDate(QDate.currentDate().addDays(30))
        self.pf_notes.clear()
        self.pf_pending_attachments = []
        self.pf_attach_label.setText("لا توجد ملفات مرفقة")
        self.set_active_nav("projects")
        self.pages.setCurrentWidget(self.page_project_form)
        self.statusBar().showMessage("مشروع جديد")

    def edit_project_form(self, project_id):
        p = self.session.query(Project).filter(Project.id == project_id).first()
        if not p:
            QMessageBox.warning(self, "تنبيه", "المشروع غير موجود.")
            return
        self.current_edit_project_id = p.id
        self.project_form_title.setText(f"تعديل مشروع #{p.id}")
        self.pf_save_btn.setText("تحديث المشروع")
        self.pf_name.setText(p.name or "")
        idx = self.pf_client_combo.findData(p.client_id)
        self.pf_client_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.pf_site.setText(p.site or "")
        self.pf_building.setText(p.building or "")
        self.pf_scope.setCurrentText(p.scope or "Fire Alarm")
        self.pf_standard.setCurrentText(p.standard or "NFPA")
        self.pf_status.setCurrentText(p.status or "Design")
        self.pf_start.setDate(to_qdate(p.start_date))
        self.pf_end.setDate(to_qdate(p.end_date))
        self.pf_notes.setPlainText(p.notes or "")
        self.pf_pending_attachments = []
        self.pf_attach_label.setText("لا توجد ملفات مرفقة")
        self.set_active_nav("projects")
        self.pages.setCurrentWidget(self.page_project_form)
        self.statusBar().showMessage(f"تعديل مشروع #{p.id}")

    def save_project_form(self):
        name = self.pf_name.text().strip()
        if not name:
            QMessageBox.warning(self, "تنبيه", "الرجاء إدخال اسم المشروع.")
            return

        if self.current_edit_project_id is None:
            p = Project(name=name)
            self.session.add(p)
        else:
            p = self.session.query(Project).filter(Project.id == self.current_edit_project_id).first()
            if not p:
                QMessageBox.warning(self, "تنبيه", "المشروع غير موجود.")
                return
            p.name = name

        p.client_id = self.pf_client_combo.currentData()
        p.site = self.pf_site.text().strip()
        p.building = self.pf_building.text().strip()
        p.scope = self.pf_scope.currentText()
        p.standard = self.pf_standard.currentText()
        p.status = self.pf_status.currentText()
        p.start_date = self.pf_start.date().toPython()
        p.end_date = self.pf_end.date().toPython()
        p.notes = self.pf_notes.toPlainText().strip()

        if not self.safe_commit("حفظ المشروع"):
            return

        if self.pf_pending_attachments:
            proj_dir = os.path.join(ATTACHMENTS_DIR, str(p.id))
            os.makedirs(proj_dir, exist_ok=True)
            for f in self.pf_pending_attachments:
                try:
                    shutil.copy2(f, proj_dir)
                except Exception as e:
                    print("Attachment copy error:", e)
            self.pf_pending_attachments = []
            self.pf_attach_label.setText("لا توجد ملفات مرفقة")

        QMessageBox.information(self, "تم الحفظ", f"تم حفظ المشروع #{p.id} بنجاح.")
        self.refresh_all()
        self.open_project_details(p.id)

    # ------------------------------------------------------------------
    # Projects: صفحة التفاصيل
    # ------------------------------------------------------------------
    def build_project_details_page(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        back_btn = QPushButton("← رجوع للمشاريع")
        back_btn.clicked.connect(self.show_projects)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        self.pd_title = QLabel("تفاصيل المشروع")
        self.pd_title.setObjectName("PageTitle")
        layout.addWidget(self.pd_title)

        card, card_layout = make_card()
        self.pd_status_badge = QLabel("")
        card_layout.addWidget(self.pd_status_badge, alignment=Qt.AlignLeft)
        self.pd_fields = QLabel("")
        self.pd_fields.setWordWrap(True)
        card_layout.addWidget(self.pd_fields)
        layout.addWidget(card)

        # ملخص مالي
        fin_card, fin_layout = make_card("الملخص المالي")
        self.pd_financial = QLabel("")
        fin_layout.addWidget(self.pd_financial)
        layout.addWidget(fin_card)

        # معدات المشروع
        eq_card, eq_layout = make_card("المعدات المرتبطة")
        self.pd_equipment_table = QTableWidget(0, 4)
        self.pd_equipment_table.setHorizontalHeaderLabels(["المعدة", "النوع", "الفحص القادم", "الحالة"])
        self.pd_equipment_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pd_equipment_table.setMaximumHeight(160)
        tune_table(self.pd_equipment_table, stretch_col=0)
        eq_layout.addWidget(self.pd_equipment_table)
        layout.addWidget(eq_card)

        btn_row = QHBoxLayout()
        view_attach_btn = QPushButton("عرض المرفقات")
        view_attach_btn.clicked.connect(self.view_attachments_for_current_project)

        report_btn = QPushButton("إنشاء تقرير PDF")
        report_btn.clicked.connect(self.generate_report_for_current_project)

        edit_btn = QPushButton("تعديل")
        edit_btn.clicked.connect(lambda: self.edit_project_form(self.current_viewed_project_id))

        delete_btn = QPushButton("حذف")
        delete_btn.setObjectName("DangerButton")
        delete_btn.clicked.connect(self.delete_current_project)

        btn_row.addWidget(view_attach_btn)
        btn_row.addWidget(report_btn)
        btn_row.addStretch()
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

        return w

    def open_project_details(self, project_id):
        p = self.session.query(Project).filter(Project.id == project_id).first()
        if not p:
            QMessageBox.warning(self, "تنبيه", "المشروع غير موجود.")
            return

        self.current_viewed_project_id = p.id
        self.pd_title.setText(f"مشروع #{p.id} — {p.name}")
        self.pd_status_badge.setText(p.status or "")
        self.pd_status_badge.setStyleSheet(status_badge_style(p.status or ""))

        txt = (
            f"العميل: {p.client_name or '-'}\n"
            f"الموقع: {p.site or '-'}\n"
            f"المبنى: {p.building or '-'}\n"
            f"نطاق النظام: {p.scope or '-'}\n"
            f"المعيار المرجعي: {p.standard or '-'}\n"
            f"تاريخ البدء: {p.start_date or '-'}\n"
            f"تاريخ الانتهاء: {p.end_date or '-'}\n"
            f"ملاحظات: {p.notes or '-'}"
        )
        self.pd_fields.setText(txt)

        self.pd_financial.setText(
            f"إجمالي الفواتير: {p.total_invoiced:,.2f}    |    غير المسدد: {p.total_unpaid:,.2f}    |    عدد الفواتير: {len(p.invoices)}"
        )

        self.pd_equipment_table.setRowCount(0)
        for e in p.equipment:
            row = self.pd_equipment_table.rowCount()
            self.pd_equipment_table.insertRow(row)
            self.pd_equipment_table.setItem(row, 0, QTableWidgetItem(e.name or ""))
            self.pd_equipment_table.setItem(row, 1, QTableWidgetItem(e.equipment_type or ""))
            nxt = e.next_inspection_date
            self.pd_equipment_table.setItem(row, 2, QTableWidgetItem(str(nxt) if nxt else "-"))
            _lvl = e.alert_level
            _txt = {"overdue": "متأخر", "soon": "قريب",
                    "none": "سليم", "unknown": "لم يُفحص"}.get(_lvl, "—")
            set_badge_cell(self.pd_equipment_table, row, 3, _txt,
                           alert_badge_style(_lvl))

        self.set_active_nav("projects")
        self.pages.setCurrentWidget(self.page_project_details)
        self.statusBar().showMessage(f"تفاصيل المشروع #{p.id}")

    def view_attachments_for_current_project(self):
        pid = self.current_viewed_project_id
        if pid is None:
            return
        folder = os.path.join(ATTACHMENTS_DIR, str(pid))
        if not os.path.exists(folder):
            QMessageBox.information(self, "المرفقات", "لا يوجد مجلد مرفقات لهذا المشروع.")
            return
        files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        if not files:
            QMessageBox.information(self, "المرفقات", "لا توجد مرفقات.")
            return
        dlg = QMessageBox(self)
        dlg.setWindowTitle("المرفقات")
        dlg.setText("اختر ملفًا لفتحه:")
        buttons = {}
        for fname in files[:10]:
            btn = dlg.addButton(fname, QMessageBox.ActionRole)
            buttons[btn] = fname
        dlg.addButton("إغلاق", QMessageBox.RejectRole)
        dlg.exec()
        clicked = dlg.clickedButton()
        if clicked in buttons:
            path = os.path.join(folder, buttons[clicked])
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def generate_report_for_current_project(self):
        pid = self.current_viewed_project_id
        if pid is None:
            return
        p = self.session.query(Project).filter(Project.id == pid).first()
        if not p:
            QMessageBox.warning(self, "التقرير", "المشروع غير موجود.")
            return
        report_path = os.path.join(REPORTS_DIR, f"Project_{p.id}_Report.pdf")
        try:
            reports_module.generate_project_report_pdf(p, report_path)
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر إنشاء التقرير:\n{e}")
            return
        QMessageBox.information(self, "التقرير", f"تم إنشاء التقرير:\n{report_path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(report_path))

    def delete_current_project(self):
        pid = self.current_viewed_project_id
        if pid is None:
            return
        reply = QMessageBox.question(
            self, "تأكيد الحذف", f"هل تريد حذف المشروع #{pid}؟ سيتم حذف الفواتير والمعدات المرتبطة به أيضًا.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        p = self.session.query(Project).filter(Project.id == pid).first()
        if not p:
            return
        self.session.delete(p)
        if not self.safe_commit("حذف المشروع"):
            return
        folder = os.path.join(ATTACHMENTS_DIR, str(pid))
        if os.path.exists(folder):
            shutil.rmtree(folder, ignore_errors=True)
        QMessageBox.information(self, "تم الحذف", f"تم حذف المشروع #{pid}.")
        self.refresh_all()
        self.show_projects()

    # ------------------------------------------------------------------
    # Clients
    # ------------------------------------------------------------------
    def build_clients_page(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.page_header(layout, "العملاء", "إدارة بيانات العملاء وربطهم بالمشاريع")

        body = QHBoxLayout()

        # القائمة على اليمين
        list_card, list_layout = make_card()
        search_row = QHBoxLayout()
        self.client_search = QLineEdit()
        self.client_search.setPlaceholderText("ابحث عن عميل...")
        self.client_search.textChanged.connect(self.refresh_clients_table)
        new_client_btn = QPushButton("+ عميل جديد")
        new_client_btn.setObjectName("PrimaryButton")
        new_client_btn.clicked.connect(self.new_client_form)
        search_row.addWidget(self.client_search)
        search_row.addWidget(new_client_btn)
        list_layout.addLayout(search_row)

        self.clients_table = QTableWidget(0, 4)
        self.clients_table.setHorizontalHeaderLabels(["الاسم", "الهاتف", "البريد الإلكتروني", "عدد المشاريع"])
        self.clients_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.clients_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.clients_table.itemClicked.connect(self.load_client_for_edit_from_table)
        tune_table(self.clients_table, stretch_col=0)
        list_layout.addWidget(self.clients_table)
        body.addWidget(list_card, 3)

        # نموذج على اليسار
        form_card, form_layout = make_card()
        self.client_form_title = QLabel("عميل جديد")
        self.client_form_title.setObjectName("PageSubtitle")
        form_layout.addWidget(self.client_form_title)

        form = QFormLayout()
        self.cf_name = QLineEdit()
        self.cf_contact = QLineEdit()
        self.cf_phone = QLineEdit()
        self.cf_email = QLineEdit()
        self.cf_address = QLineEdit()
        self.cf_notes = QTextEdit()
        self.cf_notes.setMaximumHeight(80)

        form.addRow("اسم العميل *", self.cf_name)
        form.addRow("مسؤول التواصل", self.cf_contact)
        form.addRow("الهاتف", self.cf_phone)
        form.addRow("البريد الإلكتروني", self.cf_email)
        form.addRow("العنوان", self.cf_address)
        form.addRow("ملاحظات", self.cf_notes)
        form_layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.cf_save_btn = QPushButton("حفظ العميل")
        self.cf_save_btn.setObjectName("PrimaryButton")
        self.cf_save_btn.clicked.connect(self.save_client_form)
        clear_btn = QPushButton("جديد")
        clear_btn.clicked.connect(self.new_client_form)
        delete_btn = QPushButton("حذف")
        delete_btn.setObjectName("DangerButton")
        delete_btn.clicked.connect(self.delete_current_client)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(self.cf_save_btn)
        form_layout.addLayout(btn_row)
        form_layout.addStretch()

        body.addWidget(form_card, 2)
        layout.addLayout(body)
        return w

    def new_client_form(self):
        self.current_edit_client_id = None
        self.client_form_title.setText("عميل جديد")
        self.cf_save_btn.setText("حفظ العميل")
        self.cf_name.clear()
        self.cf_contact.clear()
        self.cf_phone.clear()
        self.cf_email.clear()
        self.cf_address.clear()
        self.cf_notes.clear()

    def load_client_for_edit_from_table(self, item):
        row = item.row()
        client_id = self.clients_table.item(row, 0).data(Qt.UserRole)
        if client_id is None:
            return
        c = self.session.query(Client).filter(Client.id == client_id).first()
        if not c:
            return
        self.current_edit_client_id = c.id
        self.client_form_title.setText(f"تعديل عميل #{c.id}")
        self.cf_save_btn.setText("تحديث العميل")
        self.cf_name.setText(c.name or "")
        self.cf_contact.setText(c.contact_person or "")
        self.cf_phone.setText(c.phone or "")
        self.cf_email.setText(c.email or "")
        self.cf_address.setText(c.address or "")
        self.cf_notes.setPlainText(c.notes or "")

    def save_client_form(self):
        name = self.cf_name.text().strip()
        if not name:
            QMessageBox.warning(self, "تنبيه", "الرجاء إدخال اسم العميل.")
            return
        if self.current_edit_client_id is None:
            c = Client(name=name)
            self.session.add(c)
        else:
            c = self.session.query(Client).filter(Client.id == self.current_edit_client_id).first()
            if not c:
                QMessageBox.warning(self, "تنبيه", "العميل غير موجود.")
                return
            c.name = name
        c.contact_person = self.cf_contact.text().strip()
        c.phone = self.cf_phone.text().strip()
        c.email = self.cf_email.text().strip()
        c.address = self.cf_address.text().strip()
        c.notes = self.cf_notes.toPlainText().strip()
        if not self.safe_commit("حفظ العميل"):
            return
        QMessageBox.information(self, "تم الحفظ", f"تم حفظ العميل #{c.id} بنجاح.")
        self.refresh_all()
        self.new_client_form()

    def delete_current_client(self):
        if self.current_edit_client_id is None:
            QMessageBox.information(self, "معلومة", "اختر عميلًا من القائمة أولًا.")
            return
        c = self.session.query(Client).filter(Client.id == self.current_edit_client_id).first()
        if not c:
            return
        if c.projects:
            QMessageBox.warning(
                self, "تعذر الحذف",
                f"لا يمكن حذف هذا العميل لأنه مرتبط بـ {len(c.projects)} مشروع(مشاريع). "
                "قم بإزالة الربط أو حذف المشاريع أولًا."
            )
            return
        reply = QMessageBox.question(self, "تأكيد الحذف", f"حذف العميل '{c.name}'؟", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.session.delete(c)
        if not self.safe_commit("حذف العميل"):
            return
        QMessageBox.information(self, "تم الحذف", "تم حذف العميل.")
        self.refresh_all()
        self.new_client_form()

    def refresh_clients_table(self):
        text = self.client_search.text().strip()
        q = self.session.query(Client)
        if text:
            like = f"%{text}%"
            q = q.filter(Client.name.ilike(like))
        rows = q.order_by(Client.name.asc()).all()
        self.clients_table.setRowCount(0)
        for c in rows:
            row = self.clients_table.rowCount()
            self.clients_table.insertRow(row)
            name_item = QTableWidgetItem(c.name or "")
            name_item.setData(Qt.UserRole, c.id)
            self.clients_table.setItem(row, 0, name_item)
            self.clients_table.setItem(row, 1, QTableWidgetItem(c.phone or ""))
            self.clients_table.setItem(row, 2, QTableWidgetItem(c.email or ""))
            self.clients_table.setItem(row, 3, QTableWidgetItem(str(len(c.projects))))

    # ------------------------------------------------------------------
    # Equipment & Inspections
    # ------------------------------------------------------------------
    def build_equipment_page(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.page_header(layout, "المعدات والفحص الدوري", "تتبّع معدات الحماية من الحريق ومواعيد الفحص القادمة")

        body = QHBoxLayout()

        list_card, list_layout = make_card()
        top_row = QHBoxLayout()
        self.equipment_search = QLineEdit()
        self.equipment_search.setPlaceholderText("ابحث عن معدة...")
        self.equipment_search.textChanged.connect(self.refresh_equipment_table)
        new_eq_btn = QPushButton("+ معدة جديدة")
        new_eq_btn.setObjectName("PrimaryButton")
        new_eq_btn.clicked.connect(self.new_equipment_form)
        top_row.addWidget(self.equipment_search)
        top_row.addWidget(new_eq_btn)
        list_layout.addLayout(top_row)

        self.equipment_table = QTableWidget(0, 6)
        self.equipment_table.setHorizontalHeaderLabels(
            ["المعدة", "المشروع", "النوع", "الفحص القادم", "الحالة", "تنبيه"]
        )
        self.equipment_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.equipment_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.equipment_table.itemClicked.connect(self.load_equipment_for_edit_from_table)
        tune_table(self.equipment_table, stretch_col=0)
        list_layout.addWidget(self.equipment_table)
        body.addWidget(list_card, 3)

        form_card, form_layout = make_card()
        self.equipment_form_title = QLabel("معدة جديدة")
        self.equipment_form_title.setObjectName("PageSubtitle")
        form_layout.addWidget(self.equipment_form_title)

        form = QFormLayout()
        self.ef_project_combo = QComboBox()
        self.ef_name = QLineEdit()
        self.ef_type = QComboBox()
        self.ef_type.setEditable(True)
        self.ef_type.addItems([
            "طفاية حريق", "مضخة حريق", "لوحة إنذار", "كاشف دخان",
            "رأس رشاش", "صندوق خرطوم", "نظام إطفاء غازي"
        ])
        self.ef_location = QLineEdit()
        self.ef_last_inspection = QDateEdit()
        self.ef_last_inspection.setCalendarPopup(True)
        self.ef_last_inspection.setDate(QDate.currentDate())
        self.ef_interval = QSpinBox()
        self.ef_interval.setRange(1, 3650)
        self.ef_interval.setValue(180)
        self.ef_interval.setSuffix(" يوم")
        self.ef_status = QComboBox()
        self.ef_status.addItems(["OK", "Needs Attention", "Faulty"])
        self.ef_notes = QTextEdit()
        self.ef_notes.setMaximumHeight(70)

        form.addRow("المشروع *", self.ef_project_combo)
        form.addRow("اسم المعدة *", self.ef_name)
        form.addRow("النوع", self.ef_type)
        form.addRow("الموقع", self.ef_location)
        form.addRow("تاريخ آخر فحص", self.ef_last_inspection)
        form.addRow("دورة الفحص", self.ef_interval)
        form.addRow("الحالة", self.ef_status)
        form.addRow("ملاحظات", self.ef_notes)
        form_layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.ef_save_btn = QPushButton("حفظ")
        self.ef_save_btn.setObjectName("PrimaryButton")
        self.ef_save_btn.clicked.connect(self.save_equipment_form)
        clear_btn = QPushButton("جديد")
        clear_btn.clicked.connect(self.new_equipment_form)
        delete_btn = QPushButton("حذف")
        delete_btn.setObjectName("DangerButton")
        delete_btn.clicked.connect(self.delete_current_equipment)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(self.ef_save_btn)
        form_layout.addLayout(btn_row)
        form_layout.addStretch()

        body.addWidget(form_card, 2)
        layout.addLayout(body)
        return w

    def new_equipment_form(self):
        self.current_edit_equipment_id = None
        self.equipment_form_title.setText("معدة جديدة")
        self.ef_save_btn.setText("حفظ")
        if self.ef_project_combo.count():
            self.ef_project_combo.setCurrentIndex(0)
        self.ef_name.clear()
        self.ef_type.setCurrentIndex(0)
        self.ef_location.clear()
        self.ef_last_inspection.setDate(QDate.currentDate())
        self.ef_interval.setValue(180)
        self.ef_status.setCurrentIndex(0)
        self.ef_notes.clear()

    def load_equipment_for_edit_from_table(self, item):
        row = item.row()
        eq_id = self.equipment_table.item(row, 0).data(Qt.UserRole)
        if eq_id is None:
            return
        e = self.session.query(Equipment).filter(Equipment.id == eq_id).first()
        if not e:
            return
        self.current_edit_equipment_id = e.id
        self.equipment_form_title.setText(f"تعديل معدة #{e.id}")
        self.ef_save_btn.setText("تحديث")
        idx = self.ef_project_combo.findData(e.project_id)
        self.ef_project_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.ef_name.setText(e.name or "")
        self.ef_type.setCurrentText(e.equipment_type or "")
        self.ef_location.setText(e.location or "")
        self.ef_last_inspection.setDate(to_qdate(e.last_inspection_date))
        self.ef_interval.setValue(e.interval_days or 180)
        self.ef_status.setCurrentText(e.status or "OK")
        self.ef_notes.setPlainText(e.notes or "")

    def save_equipment_form(self):
        name = self.ef_name.text().strip()
        project_id = self.ef_project_combo.currentData()
        if not name:
            QMessageBox.warning(self, "تنبيه", "الرجاء إدخال اسم المعدة.")
            return
        if not project_id:
            if self.ef_project_combo.count() == 0:
                QMessageBox.warning(
                    self, "لا توجد مشاريع",
                    "لا يمكن إضافة معدة قبل إنشاء مشروع.\n"
                    "أنشئ مشروعًا أولًا من صفحة المشاريع ثم عد إلى هنا."
                )
            else:
                QMessageBox.warning(self, "تنبيه", "الرجاء اختيار المشروع المرتبط بالمعدة.")
            return

        if self.current_edit_equipment_id is None:
            e = Equipment(name=name, project_id=project_id)
            self.session.add(e)
        else:
            e = self.session.query(Equipment).filter(Equipment.id == self.current_edit_equipment_id).first()
            if not e:
                QMessageBox.warning(self, "تنبيه", "المعدة غير موجودة.")
                return
            e.name = name
            e.project_id = project_id

        e.equipment_type = self.ef_type.currentText().strip()
        e.location = self.ef_location.text().strip()
        e.last_inspection_date = self.ef_last_inspection.date().toPython()
        e.interval_days = self.ef_interval.value()
        e.status = self.ef_status.currentText()
        e.notes = self.ef_notes.toPlainText().strip()
        if not self.safe_commit("حفظ المعدة"):
            return
        QMessageBox.information(self, "تم الحفظ", f"تم حفظ المعدة #{e.id} بنجاح.")
        self.refresh_all()
        self.new_equipment_form()

    def delete_current_equipment(self):
        if self.current_edit_equipment_id is None:
            QMessageBox.information(self, "معلومة", "اختر معدة من القائمة أولًا.")
            return
        e = self.session.query(Equipment).filter(Equipment.id == self.current_edit_equipment_id).first()
        if not e:
            return
        reply = QMessageBox.question(self, "تأكيد الحذف", f"حذف المعدة '{e.name}'؟", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.session.delete(e)
        if not self.safe_commit("حذف المعدة"):
            return
        QMessageBox.information(self, "تم الحذف", "تم حذف المعدة.")
        self.refresh_all()
        self.new_equipment_form()

    def refresh_equipment_table(self):
        text = self.equipment_search.text().strip()
        q = self.session.query(Equipment)
        if text:
            like = f"%{text}%"
            q = q.filter(or_(
                Equipment.name.ilike(like),
                Equipment.equipment_type.ilike(like),
                Equipment.location.ilike(like),
            ))
        rows = q.order_by(Equipment.id.desc()).all()
        self.equipment_table.setRowCount(0)
        for e in rows:
            row = self.equipment_table.rowCount()
            self.equipment_table.insertRow(row)
            name_item = QTableWidgetItem(e.name or "")
            name_item.setData(Qt.UserRole, e.id)
            self.equipment_table.setItem(row, 0, name_item)
            self.equipment_table.setItem(row, 1, QTableWidgetItem(e.project.name if e.project else ""))
            self.equipment_table.setItem(row, 2, QTableWidgetItem(e.equipment_type or ""))
            nxt = e.next_inspection_date
            self.equipment_table.setItem(row, 3, QTableWidgetItem(str(nxt) if nxt else "-"))
            self.equipment_table.setItem(row, 4, QTableWidgetItem(e.status or ""))
            level = e.alert_level
            # "unknown" = لم يُسجَّل تاريخ فحص. بدون .get() كان البرنامج
            # ينهار بـ KeyError على أي معدة بلا تاريخ فحص.
            badge_text = {"overdue": "متأخر", "soon": "قريب",
                          "none": "سليم", "unknown": "لم يُفحص"}.get(level, "—")
            set_badge_cell(self.equipment_table, row, 5, badge_text,
                           alert_badge_style(level))

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------
    def build_invoices_page(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.page_header(layout, "الفواتير", "إصدار ومتابعة فواتير المشاريع")

        body = QHBoxLayout()

        list_card, list_layout = make_card()
        top_row = QHBoxLayout()
        self.invoice_search = QLineEdit()
        self.invoice_search.setPlaceholderText("ابحث برقم الفاتورة أو المشروع...")
        self.invoice_search.textChanged.connect(self.refresh_invoices_table)
        self.invoice_status_filter = QComboBox()
        self.invoice_status_filter.addItem("كل الفواتير", "")
        self.invoice_status_filter.addItem("غير مسددة", "Unpaid")
        self.invoice_status_filter.addItem("مسددة", "Paid")
        self.invoice_status_filter.addItem("متأخرة", "Overdue")
        self.invoice_status_filter.currentIndexChanged.connect(self.refresh_invoices_table)
        new_inv_btn = QPushButton("+ فاتورة جديدة")
        new_inv_btn.setObjectName("PrimaryButton")
        new_inv_btn.clicked.connect(self.new_invoice_form)
        top_row.addWidget(self.invoice_search)
        top_row.addWidget(self.invoice_status_filter)
        top_row.addWidget(new_inv_btn)
        list_layout.addLayout(top_row)

        self.invoices_table = QTableWidget(0, 5)
        self.invoices_table.setHorizontalHeaderLabels(["رقم الفاتورة", "المشروع", "المبلغ", "الاستحقاق", "الحالة"])
        self.invoices_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.invoices_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.invoices_table.itemClicked.connect(self.load_invoice_for_edit_from_table)
        tune_table(self.invoices_table, stretch_col=1)
        list_layout.addWidget(self.invoices_table)
        body.addWidget(list_card, 3)

        form_card, form_layout = make_card()
        self.invoice_form_title = QLabel("فاتورة جديدة")
        self.invoice_form_title.setObjectName("PageSubtitle")
        form_layout.addWidget(self.invoice_form_title)

        form = QFormLayout()
        self.if_project_combo = QComboBox()
        self.if_number = QLineEdit()
        self.if_number.setPlaceholderText("مثال: INV-2026-001")
        self.if_amount = QDoubleSpinBox()
        self.if_amount.setRange(0, 100_000_000)
        self.if_amount.setDecimals(2)
        self.if_amount.setSuffix(" ريال")
        self.if_issue_date = QDateEdit()
        self.if_issue_date.setCalendarPopup(True)
        self.if_issue_date.setDate(QDate.currentDate())
        self.if_due_date = QDateEdit()
        self.if_due_date.setCalendarPopup(True)
        self.if_due_date.setDate(QDate.currentDate().addDays(30))
        self.if_status = QComboBox()
        self.if_status.addItems(["Unpaid", "Paid"])
        self.if_notes = QTextEdit()
        self.if_notes.setMaximumHeight(70)

        form.addRow("المشروع *", self.if_project_combo)
        form.addRow("رقم الفاتورة", self.if_number)
        form.addRow("المبلغ", self.if_amount)
        form.addRow("تاريخ الإصدار", self.if_issue_date)
        form.addRow("تاريخ الاستحقاق", self.if_due_date)
        form.addRow("الحالة", self.if_status)
        form.addRow("ملاحظات", self.if_notes)
        form_layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.if_save_btn = QPushButton("حفظ")
        self.if_save_btn.setObjectName("PrimaryButton")
        self.if_save_btn.clicked.connect(self.save_invoice_form)
        clear_btn = QPushButton("جديد")
        clear_btn.clicked.connect(self.new_invoice_form)
        delete_btn = QPushButton("حذف")
        delete_btn.setObjectName("DangerButton")
        delete_btn.clicked.connect(self.delete_current_invoice)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(self.if_save_btn)
        form_layout.addLayout(btn_row)
        form_layout.addStretch()

        body.addWidget(form_card, 2)
        layout.addLayout(body)
        return w

    def new_invoice_form(self):
        self.current_edit_invoice_id = None
        self.invoice_form_title.setText("فاتورة جديدة")
        self.if_save_btn.setText("حفظ")
        if self.if_project_combo.count():
            self.if_project_combo.setCurrentIndex(0)
        self.if_number.clear()
        self.if_amount.setValue(0)
        self.if_issue_date.setDate(QDate.currentDate())
        self.if_due_date.setDate(QDate.currentDate().addDays(30))
        self.if_status.setCurrentIndex(0)
        self.if_notes.clear()

    def load_invoice_for_edit_from_table(self, item):
        row = item.row()
        inv_id = self.invoices_table.item(row, 0).data(Qt.UserRole)
        if inv_id is None:
            return
        i = self.session.query(Invoice).filter(Invoice.id == inv_id).first()
        if not i:
            return
        self.current_edit_invoice_id = i.id
        self.invoice_form_title.setText(f"تعديل فاتورة #{i.id}")
        self.if_save_btn.setText("تحديث")
        idx = self.if_project_combo.findData(i.project_id)
        self.if_project_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.if_number.setText(i.invoice_number or "")
        self.if_amount.setValue(i.amount or 0)
        self.if_issue_date.setDate(to_qdate(i.issue_date))
        self.if_due_date.setDate(to_qdate(i.due_date))
        self.if_status.setCurrentText(i.status or "Unpaid")
        self.if_notes.setPlainText(i.notes or "")

    def save_invoice_form(self):
        project_id = self.if_project_combo.currentData()
        if not project_id:
            if self.if_project_combo.count() == 0:
                QMessageBox.warning(
                    self, "لا توجد مشاريع",
                    "لا يمكن إصدار فاتورة قبل إنشاء مشروع.\n"
                    "أنشئ مشروعًا أولًا من صفحة المشاريع ثم عد إلى هنا."
                )
            else:
                QMessageBox.warning(self, "تنبيه", "الرجاء اختيار المشروع.")
            return

        if self.current_edit_invoice_id is None:
            i = Invoice(project_id=project_id)
            self.session.add(i)
        else:
            i = self.session.query(Invoice).filter(Invoice.id == self.current_edit_invoice_id).first()
            if not i:
                QMessageBox.warning(self, "تنبيه", "الفاتورة غير موجودة.")
                return
            i.project_id = project_id

        i.invoice_number = self.if_number.text().strip()
        i.amount = self.if_amount.value()
        i.issue_date = self.if_issue_date.date().toPython()
        i.due_date = self.if_due_date.date().toPython()
        i.status = self.if_status.currentText()
        i.notes = self.if_notes.toPlainText().strip()
        if not self.safe_commit("حفظ الفاتورة"):
            return
        QMessageBox.information(self, "تم الحفظ", f"تم حفظ الفاتورة #{i.id} بنجاح.")
        self.refresh_all()
        self.new_invoice_form()

    def delete_current_invoice(self):
        if self.current_edit_invoice_id is None:
            QMessageBox.information(self, "معلومة", "اختر فاتورة من القائمة أولًا.")
            return
        i = self.session.query(Invoice).filter(Invoice.id == self.current_edit_invoice_id).first()
        if not i:
            return
        reply = QMessageBox.question(self, "تأكيد الحذف", f"حذف الفاتورة '{i.invoice_number or i.id}'؟", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.session.delete(i)
        if not self.safe_commit("حذف الفاتورة"):
            return
        QMessageBox.information(self, "تم الحذف", "تم حذف الفاتورة.")
        self.refresh_all()
        self.new_invoice_form()

    def refresh_invoices_table(self):
        text = self.invoice_search.text().strip()
        status = self.invoice_status_filter.currentData() or ""
        q = self.session.query(Invoice)
        if text:
            like = f"%{text}%"
            q = q.join(Project).filter(or_(
                Invoice.invoice_number.ilike(like),
                Project.name.ilike(like),
            ))
        if status == "Overdue":
            rows = [i for i in q.all() if i.is_overdue]
        else:
            if status:
                q = q.filter(Invoice.status == status)
            rows = q.order_by(Invoice.due_date.asc()).all()

        self.invoices_table.setRowCount(0)
        for i in rows:
            row = self.invoices_table.rowCount()
            self.invoices_table.insertRow(row)
            num_item = QTableWidgetItem(i.invoice_number or f"#{i.id}")
            num_item.setData(Qt.UserRole, i.id)
            self.invoices_table.setItem(row, 0, num_item)
            self.invoices_table.setItem(row, 1, QTableWidgetItem(i.project.name if i.project else ""))
            self.invoices_table.setItem(row, 2, QTableWidgetItem(f"{i.amount:,.2f}" if i.amount else "0.00"))
            self.invoices_table.setItem(row, 3, QTableWidgetItem(str(i.due_date) if i.due_date else "-"))
            if i.is_overdue:
                set_badge_cell(self.invoices_table, row, 4, "متأخرة",
                               alert_badge_style("overdue"))
            else:
                _txt = "مسددة" if i.status == "Paid" else "غير مسددة"
                _lvl = "none" if i.status == "Paid" else "soon"
                set_badge_cell(self.invoices_table, row, 4, _txt,
                               alert_badge_style(_lvl))

    # ------------------------------------------------------------------
    # Reports (PDF + CSV exports)
    # ------------------------------------------------------------------
    def build_reports_page(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.page_header(layout, "التقارير", "تقارير PDF للمشاريع والفحوصات الدورية، وتصدير CSV شامل")

        pdf_card, pdf_layout = make_card("تقرير PDF لمشروع")
        row = QHBoxLayout()
        self.report_project_combo = QComboBox()
        gen_btn = QPushButton("إنشاء التقرير")
        gen_btn.setObjectName("PrimaryButton")
        gen_btn.clicked.connect(self.generate_report_from_reports_page)
        row.addWidget(self.report_project_combo, 3)
        row.addWidget(gen_btn, 1)
        pdf_layout.addLayout(row)
        layout.addWidget(pdf_card)

        insp_card, insp_layout = make_card("تقرير الفحوصات (للدفاع المدني)")
        insp_row = QHBoxLayout()
        self.insp_scope_combo = QComboBox()
        self.insp_scope_combo.addItem("كل المعدات", "all")
        self.insp_scope_combo.addItem("المستحقة والمتأخرة فقط (خلال 30 يومًا)", "due")
        self.insp_scope_combo.addItem("المتأخرة فقط", "overdue")
        self.insp_scope_combo.addItem("مشروع محدد…", "project")
        self.insp_project_combo = QComboBox()
        self.insp_project_combo.setEnabled(False)
        self.insp_scope_combo.currentIndexChanged.connect(
            lambda: self.insp_project_combo.setEnabled(
                self.insp_scope_combo.currentData() == "project"
            )
        )
        insp_btn = QPushButton("إنشاء تقرير الفحوصات")
        insp_btn.setObjectName("PrimaryButton")
        insp_btn.clicked.connect(self.generate_inspections_report)
        insp_row.addWidget(self.insp_scope_combo, 3)
        insp_row.addWidget(self.insp_project_combo, 3)
        insp_row.addWidget(insp_btn, 2)
        insp_layout.addLayout(insp_row)
        layout.addWidget(insp_card)

        sum_card, sum_layout = make_card("التقرير الشامل لكل المشاريع")
        sum_row = QHBoxLayout()
        self.summary_status_combo = QComboBox()
        self.summary_status_combo.addItem("كل الحالات", "")
        for _st in PROJECT_STATUSES:
            self.summary_status_combo.addItem(_st, _st)
        sum_btn = QPushButton("إنشاء التقرير الشامل")
        sum_btn.setObjectName("PrimaryButton")
        sum_btn.clicked.connect(self.generate_projects_summary_report)
        sum_row.addWidget(self.summary_status_combo, 3)
        sum_row.addWidget(sum_btn, 2)
        sum_layout.addLayout(sum_row)
        layout.addWidget(sum_card)

        csv_card, csv_layout = make_card("تصدير CSV")
        csv_row = QHBoxLayout()
        exp_projects = QPushButton("تصدير المشاريع")
        exp_projects.clicked.connect(lambda: self.export_csv("projects"))
        exp_invoices = QPushButton("تصدير الفواتير")
        exp_invoices.clicked.connect(lambda: self.export_csv("invoices"))
        exp_equipment = QPushButton("تصدير المعدات")
        exp_equipment.clicked.connect(lambda: self.export_csv("equipment"))
        csv_row.addWidget(exp_projects)
        csv_row.addWidget(exp_invoices)
        csv_row.addWidget(exp_equipment)
        csv_layout.addLayout(csv_row)
        layout.addWidget(csv_card)

        folder_card, folder_layout = make_card("المجلدات")
        open_reports_btn = QPushButton("فتح مجلد التقارير")
        open_reports_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(REPORTS_DIR)))
        open_backups_btn = QPushButton("فتح مجلد النسخ الاحتياطية")
        open_backups_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(BACKUPS_DIR)))
        f_row = QHBoxLayout()
        f_row.addWidget(open_reports_btn)
        f_row.addWidget(open_backups_btn)
        folder_layout.addLayout(f_row)
        layout.addWidget(folder_card)

        layout.addStretch()
        return w

    def generate_report_from_reports_page(self):
        pid = self.report_project_combo.currentData()
        if not pid:
            QMessageBox.information(self, "معلومة", "اختر مشروعًا أولًا.")
            return
        p = self.session.query(Project).filter(Project.id == pid).first()
        if not p:
            return
        report_path = os.path.join(REPORTS_DIR, f"Project_{p.id}_Report.pdf")
        try:
            reports_module.generate_project_report_pdf(p, report_path)
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر إنشاء التقرير:\n{e}")
            return
        QMessageBox.information(self, "التقرير", f"تم إنشاء التقرير:\n{report_path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(report_path))

    def _finish_report(self, report_path):
        QMessageBox.information(self, "التقرير", f"تم إنشاء التقرير:\n{report_path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(report_path))

    def generate_inspections_report(self):
        scope = self.insp_scope_combo.currentData()
        q = self.session.query(Equipment)
        suffix = "All"

        if scope == "project":
            pid = self.insp_project_combo.currentData()
            if not pid:
                QMessageBox.information(self, "معلومة", "اختر مشروعًا أولًا.")
                return
            q = q.filter(Equipment.project_id == pid)
            suffix = f"Project_{pid}"

        items = q.order_by(Equipment.project_id.asc(), Equipment.id.asc()).all()

        if scope == "due":
            # المتأخرة + التي يستحق فحصها خلال 30 يومًا + غير المفحوصة أبدًا
            items = [e for e in items if e.alert_level in ("overdue", "soon", "unknown")]
            suffix = "Due"
        elif scope == "overdue":
            items = [e for e in items if e.alert_level == "overdue"]
            suffix = "Overdue"

        if not items:
            QMessageBox.information(self, "معلومة", "لا توجد معدات مطابقة لهذا الاختيار.")
            return

        titles = {
            "all": "تقرير الفحوصات الدورية للمعدات",
            "due": "تقرير الفحوصات المستحقة والمتأخرة",
            "overdue": "تقرير الفحوصات المتأخرة",
            "project": "تقرير الفحوصات الدورية للمعدات",
        }
        report_path = os.path.join(REPORTS_DIR, f"Inspections_{suffix}.pdf")
        try:
            reports_module.generate_inspections_report_pdf(
                items, report_path, title=titles.get(scope, titles["all"])
            )
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر إنشاء التقرير:\n{e}")
            return
        self._finish_report(report_path)

    def generate_projects_summary_report(self):
        status = self.summary_status_combo.currentData()
        q = self.session.query(Project)
        if status:
            q = q.filter(Project.status == status)
        projects = q.order_by(Project.id.asc()).all()

        if not projects:
            QMessageBox.information(self, "معلومة", "لا توجد مشاريع مطابقة لهذا الاختيار.")
            return

        title = "التقرير الشامل للمشاريع"
        if status:
            title = f"التقرير الشامل للمشاريع — {status}"
        report_path = os.path.join(
            REPORTS_DIR, f"Projects_Summary_{status or 'All'}.pdf"
        )
        try:
            reports_module.generate_projects_summary_pdf(projects, report_path, title=title)
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر إنشاء التقرير:\n{e}")
            return
        self._finish_report(report_path)

    def export_csv(self, kind):
        import csv as csv_module

        default_name = {
            "projects": "projects_export.csv",
            "invoices": "invoices_export.csv",
            "equipment": "equipment_export.csv",
        }[kind]
        path, _ = QFileDialog.getSaveFileName(self, "حفظ الملف", default_name, "CSV Files (*.csv)")
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv_module.writer(f)
                if kind == "projects":
                    writer.writerow(["ID", "Name", "Client", "Site", "Building", "Scope", "Standard", "Status", "Start", "End", "Notes"])
                    for p in self.session.query(Project).order_by(Project.id.asc()).all():
                        writer.writerow([p.id, p.name, p.client_name, p.site, p.building, p.scope, p.standard, p.status, p.start_date, p.end_date, p.notes])
                elif kind == "invoices":
                    writer.writerow(["ID", "Project", "InvoiceNumber", "Amount", "IssueDate", "DueDate", "Status"])
                    for i in self.session.query(Invoice).order_by(Invoice.id.asc()).all():
                        # الحالة الفعلية: الفاتورة المتأخرة كانت تُصدَّر كـ "Unpaid"
                        # فلا يمكن تمييز المتأخر في Excel
                        eff_status = "Overdue" if i.is_overdue else i.status
                        writer.writerow([i.id, i.project.name if i.project else "", i.invoice_number,
                                         i.amount, i.issue_date, i.due_date, eff_status])
                elif kind == "equipment":
                    writer.writerow(["ID", "Project", "Name", "Type", "Location", "LastInspection", "IntervalDays", "NextInspection", "Status"])
                    for e in self.session.query(Equipment).order_by(Equipment.id.asc()).all():
                        writer.writerow([e.id, e.project.name if e.project else "", e.name, e.equipment_type, e.location, e.last_inspection_date, e.interval_days, e.next_inspection_date, e.status])
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر التصدير:\n{e}")
            return

        QMessageBox.information(self, "تم التصدير", f"تم حفظ الملف:\n{path}")

    def reload_project_combos(self):
        projects = self.session.query(Project).order_by(Project.id.desc()).all()
        for combo in (self.ef_project_combo, self.if_project_combo,
                      self.report_project_combo, self.insp_project_combo):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for p in projects:
                combo.addItem(f"#{p.id} — {p.name}", p.id)
            idx = combo.findData(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def show_projects(self):
        self.set_active_nav("projects")
        self.refresh_projects_table()
        self.pages.setCurrentWidget(self.page_projects)
        self.statusBar().showMessage("المشاريع")

    def show_clients(self):
        self.set_active_nav("clients")
        self.refresh_clients_table()
        self.pages.setCurrentWidget(self.page_clients)
        self.statusBar().showMessage("العملاء")

    def show_equipment(self):
        self.set_active_nav("equipment")
        self.refresh_equipment_table()
        self.pages.setCurrentWidget(self.page_equipment)
        self.statusBar().showMessage("المعدات والفحص الدوري")

    def show_invoices(self):
        self.set_active_nav("invoices")
        self.refresh_invoices_table()
        self.pages.setCurrentWidget(self.page_invoices)
        self.statusBar().showMessage("الفواتير")

    def show_reports(self):
        self.set_active_nav("reports")
        self.pages.setCurrentWidget(self.page_reports)
        self.statusBar().showMessage("التقارير")

    def show_settings(self):
        self.set_active_nav("settings")
        self.load_settings_into_form()
        self.pages.setCurrentWidget(self.page_settings)
        self.statusBar().showMessage("إعدادات المنشأة")

    # ------------------------------------------------------------------
    # Settings (بيانات المنشأة في ترويسة التقارير)
    # ------------------------------------------------------------------
    def build_settings_page(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        self.page_header(
            outer, "إعدادات المنشأة",
            "هذه البيانات تظهر في ترويسة تقارير الـ PDF"
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        body = QVBoxLayout(inner)
        body.setContentsMargins(0, 0, 8, 0)

        row = QHBoxLayout()

        # ---------- بيانات الشركة ----------
        info_card, info_layout = make_card("بيانات الشركة")
        form = QFormLayout()
        form.setSpacing(10)

        self.st_name = QLineEdit()
        self.st_name.setPlaceholderText("مثال: مؤسسة الشريف لهندسة الحريق")
        self.st_name_en = QLineEdit()
        self.st_name_en.setPlaceholderText("Alsharief Fire Engineering Est.")
        self.st_cr = QLineEdit()
        self.st_cr.setPlaceholderText("1010xxxxxx")
        self.st_vat = QLineEdit()
        self.st_vat.setPlaceholderText("3xxxxxxxxxxxxx3")
        self.st_phone = QLineEdit()
        self.st_phone.setPlaceholderText("0501234567")
        self.st_email = QLineEdit()
        self.st_email.setPlaceholderText("info@example.com")
        self.st_website = QLineEdit()
        self.st_website.setPlaceholderText("www.example.com")
        self.st_address = QLineEdit()
        self.st_address.setPlaceholderText("الرياض - حي العليا")
        self.st_currency = QLineEdit()
        self.st_currency.setPlaceholderText("ريال")

        form.addRow("اسم الشركة (عربي)", self.st_name)
        form.addRow("اسم الشركة (إنجليزي)", self.st_name_en)
        form.addRow("السجل التجاري", self.st_cr)
        form.addRow("الرقم الضريبي", self.st_vat)
        form.addRow("الهاتف", self.st_phone)
        form.addRow("البريد الإلكتروني", self.st_email)
        form.addRow("الموقع الإلكتروني", self.st_website)
        form.addRow("العنوان", self.st_address)
        form.addRow("العملة", self.st_currency)
        info_layout.addLayout(form)
        row.addWidget(info_card, 3)

        # ---------- الشعار ----------
        logo_card, logo_layout = make_card("شعار الشركة")
        self.st_logo_preview = QLabel("لا يوجد شعار")
        self.st_logo_preview.setObjectName("PageSubtitle")
        self.st_logo_preview.setAlignment(Qt.AlignCenter)
        self.st_logo_preview.setMinimumHeight(150)
        self.st_logo_preview.setStyleSheet(
            "border:1px dashed #2a3340; border-radius:8px; padding:8px;"
        )
        logo_layout.addWidget(self.st_logo_preview)

        hint = QLabel("PNG أو JPG — يُفضّل خلفية شفافة، ولا يقل العرض عن 300 بكسل")
        hint.setObjectName("PageSubtitle")
        hint.setWordWrap(True)
        logo_layout.addWidget(hint)

        logo_btns = QHBoxLayout()
        pick_logo = QPushButton("اختيار شعار")
        pick_logo.clicked.connect(self.pick_company_logo)
        remove_logo = QPushButton("إزالة")
        remove_logo.setObjectName("DangerButton")
        remove_logo.clicked.connect(self.remove_company_logo)
        logo_btns.addWidget(pick_logo)
        logo_btns.addWidget(remove_logo)
        logo_layout.addLayout(logo_btns)
        logo_layout.addStretch()
        row.addWidget(logo_card, 2)

        body.addLayout(row)

        # ---------- تذييل التقرير ----------
        foot_card, foot_layout = make_card("تذييل التقرير")
        self.st_footer = QPlainTextEdit()
        self.st_footer.setMaximumHeight(70)
        self.st_footer.setPlaceholderText(
            "نص يظهر أسفل كل تقرير — مثال: هذا التقرير معتمد من القسم الفني."
        )
        foot_layout.addWidget(self.st_footer)
        body.addWidget(foot_card)

        # ---------- الأزرار ----------
        btn_row = QHBoxLayout()
        preview_btn = QPushButton("معاينة تجريبية للترويسة")
        preview_btn.clicked.connect(self.preview_letterhead)
        reset_btn = QPushButton("استرجاع المحفوظ")
        reset_btn.clicked.connect(self.load_settings_into_form)
        save_btn = QPushButton("حفظ الإعدادات")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save_settings_form)
        btn_row.addWidget(preview_btn)
        btn_row.addStretch()
        btn_row.addWidget(reset_btn)
        btn_row.addWidget(save_btn)
        body.addLayout(btn_row)
        body.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return w

    def _refresh_logo_preview(self):
        path = getattr(self, "_pending_logo_path", "") or ""
        if path and os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                self.st_logo_preview.setPixmap(
                    pix.scaled(240, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                return
        self.st_logo_preview.setPixmap(QPixmap())
        self.st_logo_preview.setText("لا يوجد شعار")

    def load_settings_into_form(self):
        cfg = load_settings()
        self.st_name.setText(cfg.get("company_name", ""))
        self.st_name_en.setText(cfg.get("company_name_en", ""))
        self.st_cr.setText(cfg.get("cr_number", ""))
        self.st_vat.setText(cfg.get("vat_number", ""))
        self.st_phone.setText(cfg.get("phone", ""))
        self.st_email.setText(cfg.get("email", ""))
        self.st_website.setText(cfg.get("website", ""))
        self.st_address.setText(cfg.get("address", ""))
        self.st_currency.setText(cfg.get("currency", "ريال"))
        self.st_footer.setPlainText(cfg.get("report_footer", ""))
        self._pending_logo_path = cfg.get("logo_path", "")
        self._refresh_logo_preview()

    def pick_company_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "اختر شعار الشركة", "", "Images (*.png *.jpg *.jpeg)"
        )
        if not path:
            return
        try:
            # يُنسخ إلى مجلد بيانات البرنامج حتى لا يضيع إن نُقل الأصل
            self._pending_logo_path = save_logo(path)
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر تحميل الشعار:\n{e}")
            return
        self._refresh_logo_preview()
        self.statusBar().showMessage("تم تحميل الشعار — لا تنسَ الحفظ")

    def remove_company_logo(self):
        self._pending_logo_path = clear_logo(getattr(self, "_pending_logo_path", ""))
        self._refresh_logo_preview()
        self.statusBar().showMessage("تمت إزالة الشعار — لا تنسَ الحفظ")

    def collect_settings_from_form(self):
        return {
            "company_name": self.st_name.text().strip(),
            "company_name_en": self.st_name_en.text().strip(),
            "cr_number": self.st_cr.text().strip(),
            "vat_number": self.st_vat.text().strip(),
            "phone": self.st_phone.text().strip(),
            "email": self.st_email.text().strip(),
            "website": self.st_website.text().strip(),
            "address": self.st_address.text().strip(),
            "currency": self.st_currency.text().strip() or "ريال",
            "report_footer": self.st_footer.toPlainText().strip(),
            "logo_path": getattr(self, "_pending_logo_path", "") or "",
        }

    def save_settings_form(self):
        try:
            save_settings(self.collect_settings_from_form())
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر حفظ الإعدادات:\n{e}")
            return
        QMessageBox.information(
            self, "تم الحفظ",
            "تم حفظ بيانات المنشأة.\nستظهر في ترويسة كل تقرير PDF جديد."
        )
        self.statusBar().showMessage("تم حفظ الإعدادات")

    def preview_letterhead(self):
        """
        يولّد تقريرًا تجريبيًا بالإعدادات الحالية (حتى غير المحفوظة) حتى يرى
        المستخدم شكل الترويسة قبل الاعتماد.
        """
        p = self.session.query(Project).order_by(Project.id.desc()).first()
        if not p:
            QMessageBox.information(
                self, "معاينة",
                "لا توجد مشاريع بعد. أنشئ مشروعًا أولًا لمعاينة شكل التقرير."
            )
            return
        out = os.path.join(REPORTS_DIR, "معاينة_الترويسة.pdf")
        try:
            reports_module.generate_project_report_pdf(
                p, out, settings=self.collect_settings_from_form()
            )
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر إنشاء المعاينة:\n{e}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(out))

    def closeEvent(self, event):
        self.session.close()
        event.accept()


def _app_icon():
    """أيقونة البرنامج (تظهر في شريط العنوان وشريط المهام)."""
    base = os.path.dirname(os.path.abspath(__file__))
    for name in ("app_icon.ico", "app_icon.png"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return QIcon(p)
    return QIcon()


def main():
    init_db()
    app = QApplication(sys.argv)

    # على ويندوز: معرّف تطبيق مستقل حتى لا تُجمَّع النافذة تحت أيقونة
    # بايثون العامة في شريط المهام، بل تظهر بأيقونة البرنامج الخاصة.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "AlSharief.FireEngineerAI.Desktop.1"
            )
        except Exception:
            pass

    app.setWindowIcon(_app_icon())
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
