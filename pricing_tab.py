"""
pricing_tab.py
───────────────
تبويب "التسعير والعروض" — يعني إنشاء عروض أسعار لمشاريع الحماية من الحرائق.
يعتمد على:
    - pricing_engine.py للعمليات الحسابية (التقريب، الهامش، VAT)
    - library_db.py لجلب معدات من PostgreSQL
    - نماذج FireEngineerAI الداخلية (Project, Client) لإدارة المشاريع
"""


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QComboBox, QLineEdit, QDateEdit, QMessageBox,
    QDoubleSpinBox, QSpinBox, QHeaderView, QAbstractItemView, QGroupBox,
    QTextEdit, QSplitter, QSizePolicy, QFileDialog, QFrame
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont

from sqlalchemy import or_

from library_db import get_library_session, LibraryEquipment, LibraryCategory
from pricing_engine import (
    round2,
    calculate_selling_price,
    apply_bulk_price_update,
    generate_quote_number,
    compute_quote_totals,
    build_quote_summary,
    PriceHistory,
    library_item_to_pricing_item,
)


def _make_emp_row(item_id, name, qty, unit, sp, ip, total):
    """عنصر صف تمهيدي لـ project_items الجديد."""
    return {
        "item_id": item_id,
        "name": name,
        "qty": qty,
        "unit": unit,
        "supply_cost": sp,
        "install_cost": ip,
        "total": total,
        "kind": "equipment",
    }


class PricingTab(QWidget):
    """
    تبويب التسعير والعروض — ينشئ عرض أسعار كامل.
    يظهر في اليمين ضمن QStackedWidget (يُضافة من app.py).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history = PriceHistory()
        self._current_items: list[dict] = []
        self._selected_project_id: int | None = None
        self._client_id: int | None = None
        self._current_client_name: str = ""
        self.setup_ui()

    # ── بناء الواجهة ──────────────────────────────────────────────

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── العنوان ──
        title = QLabel("التسعير والعروض")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        sub = QLabel("إنشاء عروض أسعار لمشاريع الحماية من الحرائق — Automated بحسابات دقيقة")
        sub.setObjectName("PageSubtitle")
        root.addWidget(sub)

        # ── معلومات العرض (بطاقة علوية) ──
        info_card, info_lay = self._make_card("معلومات العرض")

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("رقم العرض:"))
        self.quote_no_edit = QLineEdit()
        self.quote_no_edit.setReadOnly(True)
        self.quote_no_edit.setFixedWidth(140)
        row1.addWidget(self.quote_no_edit)
        row1.addWidget(QLabel("    تاريخ:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        row1.addWidget(self.date_edit)
        info_lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("العميل:"))
        self.client_combo = QComboBox()
        self.client_combo.setMinimumWidth(220)
        row2.addWidget(self.client_combo)
        row2.addWidget(QLabel("  المشروع:"))
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("اسم المشروع")
        self.project_name_edit.setMinimumWidth(200)
        row2.addWidget(self.project_name_edit)
        row2.addStretch()
        info_lay.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("الموقع:"))
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("العنوان أو المنطقة")
        row3.addWidget(self.location_edit)
        row3.addWidget(QLabel("  المساحة:"))
        self.area_spin = QDoubleSpinBox()
        self.area_spin.setSuffix(" م²")
        self.area_spin.setDecimals(0)
        self.area_spin.setRange(0, 100000)
        self.area_spin.setSingleStep(100)
        row3.addWidget(self.area_spin)
        row3.addWidget(QLabel("  الطوابق:"))
        self.floors_spin = QSpinBox()
        self.floors_spin.setRange(0, 100)
        row3.addWidget(self.floors_spin)
        row3.addStretch()
        info_lay.addLayout(row3)

        root.addLayout(info_lay)

        # ── جدول البنود ──
        items_card, items_lay = self._make_card("بنود العرض")

        self.items_table = QTableWidget(0, 7)
        self.items_table.setHorizontalHeaderLabels([
            "الرمز", "الاسم", "الكمية", "س.الشراء\n(ر.س)", "س.التثبيت\n(ر.س)",
            "الإجمالي\n(ر.س)", "إجراءات"
        ])
        self.items_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.items_table.verticalHeader().setVisible(False)

        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        self.items_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e2e;
                alternate-background-color: #252536;
                gridline-color: #3a3a4a;
                border: 1px solid #3a3a4a;
                border-radius: 8px;
                font-size: 13px;
            }
            QTableWidget::item:selected {
                background-color: #3b4a6b;
            }
            QTableWidget::item:hover {
                background-color: #2d3548;
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

        items_lay.addWidget(self.items_table)

        # أزرار إدارة البنود
        item_btns = QHBoxLayout()
        self.btn_add_item = QPushButton("➕ إضافة معدة من المكتبة")
        self.btn_add_item.setObjectName("SecondaryButton")
        self.btn_add_item.setFixedWidth(200)
        self.btn_add_item.clicked.connect(self._show_add_item_dialog)
        item_btns.addWidget(self.btn_add_item)

        self.btn_add_material = QPushButton("➕ إضافة مادة يدوياً")
        self.btn_add_material.setObjectName("SecondaryButton")
        self.btn_add_material.setFixedWidth(190)
        self.btn_add_material.clicked.connect(self._add_material_manually)
        item_btns.addWidget(self.btn_add_material)

        self.btn_remove_selected = QPushButton("🗑️ حذف المحدّد")
        self.btn_remove_selected.setObjectName("DangerButton")
        self.btn_remove_selected.setFixedWidth(140)
        self.btn_remove_selected.clicked.connect(self._remove_selected_rows)
        item_btns.addWidget(self.btn_remove_selected)

        item_btns.addStretch()
        items_lay.addLayout(item_btns)

        root.addLayout(items_lay)

        # ── الأزرار السفلية ──
        action_row = QHBoxLayout()
        action_row.addStretch()

        self.btn_calc = QPushButton("🔢 حساب الإجماليات")
        self.btn_calc.setObjectName("PrimaryButton")
        self.btn_calc.clicked.connect(self._compute_totals)
        action_row.addWidget(self.btn_calc)

        self.btn_new_quote = QPushButton("🆕 عرض جديد")
        self.btn_new_quote.setObjectName("SecondaryButton")
        self.btn_new_quote.clicked.connect(self._new_quote)
        action_row.addWidget(self.btn_new_quote)

        self.btn_export = QPushButton("📄 تصدير كـ CSV")
        self.btn_export.setFixedWidth(140)
        self.btn_export.clicked.connect(self._export_csv)
        action_row.addWidget(self.btn_export)

        root.addLayout(action_row)

        # ── الملخص المالي (بطاقة) ──
        summary_card, summary_lay = self._make_card("الملخص المالي")

        self.lbl_base_cost = QLabel("التكلفة الأساسية: 0 ر.س")
        self.lbl_base_cost.setObjectName("StatValue")
        summary_lay.addWidget(self.lbl_base_cost)

        row = QHBoxLayout()
        row.addWidget(QLabel("النفقات العامة (8%):"))
        self.lbl_overhead = QLabel("0 ر.س")
        row.addWidget(self.lbl_overhead)
        row.addStretch()
        row.addWidget(QLabel("هامش الطوارئ (5%):"))
        self.lbl_contingency = QLabel("0 ر.س")
        row.addWidget(self.lbl_contingency)
        summary_lay.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("هامش الربح (15%):"))
        self.lbl_profit = QLabel("0 ر.س")
        row2.addWidget(self.lbl_profit)
        row2.addStretch()
        row2.addWidget(QLabel("الخصم:"))
        self.lbl_discount = QLabel("0 ر.س")
        row2.addWidget(self.lbl_discount)
        summary_lay.addLayout(row2)

        sep = QFrame()
        sep.setObjectName("Separator")
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        summary_lay.addWidget(sep)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("السعر قبل الضريبة:"))
        self.lbl_net_before_vat = QLabel("0 ر.س")
        self.lbl_net_before_vat.setObjectName("StatValue")
        row3.addWidget(self.lbl_net_before_vat)
        row3.addStretch()
        row3.addWidget(QLabel("ضريبة القيمة المضافة (15%):"))
        self.lbl_vat = QLabel("0 ر.س")
        row3.addWidget(self.lbl_vat)
        summary_lay.addLayout(row3)

        sep2 = QFrame()
        sep2.setObjectName("Separator")
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        summary_lay.addWidget(sep2)

        final_row = QHBoxLayout()
        final_row.addWidget(QLabel("الإجمالي النهائي (شامل VAT):"))
        self.lbl_grand_total = QLabel("0 ر.س")
        self.lbl_grand_total.setObjectName("StatValue")
        self.lbl_grand_total.setStyleSheet("color: #4CAF50; font-size: 28px; font-weight: 700;")
        final_row.addWidget(self.lbl_grand_total)
        final_row.addStretch()
        summary_lay.addLayout(final_row)

        root.addLayout(summary_lay)

        root.addStretch()

    # ── المساعدة الداخلية ────────────────────────────────────────

    def _make_card(self, title=None):
        """بطاقة مشابهة لـ make_card في app.py."""
        card = QGroupBox(title or "")
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        return card, layout

    def _show_add_item_dialog(self):
        """نافذة اختيار معدة من المكتبة لإضافتها للعرض."""
        try:
            session = get_library_session()
            items = (
                session.query(LibraryEquipment)
                .filter(LibraryEquipment.is_active == 1)
                .order_by(LibraryEquipment.name)
                .limit(300)
                .all()
            )

            from PySide6.QtWidgets import (
                QDialog, QDialogButtonBox, QGridLayout, QTableWidget,
                QTableWidgetItem, QHeaderView, QAbstractItemView,
            )

            dlg = QDialog(self)
            dlg.setWindowTitle("➕ إضافة معدة من المكتبة")
            dlg.setMinimumSize(720, 520)
            dlg.setLayoutDirection(Qt.RightToLeft)
            lay = QVBoxLayout(dlg)

            lbl = QLabel(f"عرض {len(items)} معدة — اختر معدة وأضفها للعرض")
            lbl.setObjectName("PageSubtitle")
            lay.addWidget(lbl)

            tbl = QTableWidget(len(items), 5)
            tbl.setHorizontalHeaderLabels(["الرمز", "الاسم", "الفئة", "س.التوريد", "س.التثبيت"])
            tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
            tbl.setSelectionMode(QAbstractItemView.SingleSelection)
            tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
            tbl.verticalHeader().setVisible(False)

            hdr = tbl.horizontalHeader()
            hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(1, QHeaderView.Stretch)

            for i, eq in enumerate(items):
                cat_name = getattr(eq, 'category_name', '') or ""
                tbl.setRowCount(i + 1)
                tbl.setItem(i, 0, QTableWidgetItem(getattr(eq, 'code', '') or ''))
                name = getattr(eq, 'name', '') or getattr(eq, 'model_ar', '') or getattr(eq, 'type_ar', '') or ''
                tbl.setItem(i, 1, QTableWidgetItem(name))
                tbl.setItem(i, 2, QTableWidgetItem(cat_name or '-'))
                sp = getattr(eq, 'supply_price_sar', 0) or 0
                ip = getattr(eq, 'install_price_sar', 0) or 0
                tbl.setItem(i, 3, QTableWidgetItem(f"{sp:,.0f}"))
                tbl.setItem(i, 4, QTableWidgetItem(f"{ip:,.0f}"))

            lay.addWidget(tbl)

            btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            btn_box.accepted.connect(dlg.accept)
            btn_box.rejected.connect(dlg.reject)
            lay.addWidget(btn_box)

            if dlg.exec() != QDialog.Accepted:
                return

            selected = tbl.selectedItems()
            if not selected:
                QMessageBox.information(self, "لا تحديد", "لم تختار أي معدة.")
                return

            row = selected[0].row()
            eq = items[row]
            if eq is None:
                return

            sp = getattr(eq, 'supply_price_sar', 0) or 0
            ip = getattr(eq, 'install_price_sar', 0) or 0
            code = getattr(eq, 'code', '') or ''
            name = getattr(eq, 'name', '') or getattr(eq, 'model_ar', '') or getattr(eq, 'type_ar', '') or code
            qty = 1

            eq_total = round2(qty * (sp + ip))

            self._current_items.append({
                "item_id": getattr(eq, 'id', 0),
                "code": code,
                "name": name,
                "qty": qty,
                "unit": "وحدة",
                "supply_price_sar": sp,
                "install_price_sar": ip,
                "total": eq_total,
                "kind": "equipment",
            })
            self._refresh_table()
            self._compute_totals()
            QMessageBox.information(self, "تم الإضافة", f"تمت إضافة «{name}» للعرض.")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"تعذّر تحميل المعدات:\n{e}")

    def _add_material_manually(self):
        """إضافة مادة يدوياً (كما في fire-pricing admin)."""
        try:
            from PySide6.QtWidgets import (
                QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
                QDoubleSpinBox, QSpinBox, QComboBox, QMessageBox
            )
            from PySide6.QtCore import Qt

            dlg = QDialog(self)
            dlg.setWindowTitle("➕ إضافة مادة يدوياً")
            dlg.setMinimumSize(420, 320)
            dlg.setLayoutDirection(Qt.RightToLeft)
            lay = QFormLayout(dlg)

            name_edit = QLineEdit()
            name_edit.setPlaceholderText("اسم المادة")
            lay.addRow("اسم المادة:", name_edit)

            qty_spin = QSpinBox()
            qty_spin.setRange(1, 99999)
            qty_spin.setValue(1)
            lay.addRow("الكمية:", qty_spin)

            unit_combo = QComboBox()
            unit_combo.addItems(["وحدة", "متر", "كجم", "مقعر", "لتر", "صندوق", "قدم"])
            lay.addRow("الوحدة:", unit_combo)

            sp_spin = QDoubleSpinBox()
            sp_spin.setRange(0, 9999999)
            sp_spin.setDecimals(2)
            sp_spin.setPrefix("ر.س ")
            lay.addRow("سعر الشراء (ر.س):", sp_spin)

            ip_spin = QDoubleSpinBox()
            ip_spin.setRange(0, 9999999)
            ip_spin.setDecimals(2)
            ip_spin.setPrefix("ر.س ")
            lay.addRow("سعر التثبيت (ر.س):", ip_spin)

            btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            btn_box.accepted.connect(dlg.accept)
            btn_box.rejected.connect(dlg.reject)
            lay.addRow(btn_box)

            if dlg.exec() != QDialog.Accepted:
                return

            m_name = name_edit.text().strip()
            if not m_name:
                QMessageBox.warning(self, "تحذير", "أدخل اسم المادة.")
                return

            qty = qty_spin.value()
            unit = unit_combo.currentText()
            sp = sp_spin.value()
            ip = ip_spin.value()
            total = round2(qty * (sp + ip))

            self._current_items.append({
                "item_id": 0,
                "code": "",
                "name": m_name,
                "qty": qty,
                "unit": unit,
                "supply_price_sar": sp,
                "install_price_sar": ip,
                "total": total,
                "kind": "material",
            })
            self._refresh_table()
            self._compute_totals()
            QMessageBox.information(self, "تم الإضافة", f"تمت إضافة «{m_name}» للعرض.")
        except RuntimeError:
            pass

    def _refresh_table(self):
        """إعادة رسم الجدول من `_current_items`."""
        self.items_table.setRowCount(len(self._current_items))
        for i, item in enumerate(self._current_items):
            self.items_table.setItem(i, 0, QTableWidgetItem(item.get("code", "")))
            name = item.get("name", "")
            self.items_table.setItem(i, 1, QTableWidgetItem(name))
            self.items_table.setItem(i, 2, QTableWidgetItem(str(item.get("qty", 0))))
            sp = item.get("supply_price_sar", 0)
            ip = item.get("install_price_sar", 0)
            total = item.get("total", 0)
            self.items_table.setItem(i, 3, QTableWidgetItem(f"{sp:,.0f}"))
            self.items_table.setItem(i, 4, QTableWidgetItem(f"{ip:,.0f}"))
            self.items_table.setItem(i, 5, QTableWidgetItem(f"{total:,.0f}"))

            # زر حذف صغير نصي داخل الخلية
            del_item = QTableWidgetItem("✕ حذف")
            del_item.setForeground(Qt.red)
            self.items_table.setItem(i, 6, del_item)

        self.items_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )

    def _remove_selected_rows(self):
        """حذف الصفوف المحدّدة."""
        try:
            selected = self.items_table.selectedItems()
            if not selected:
                QMessageBox.information(self, "لا تحديد", "اختر صفوفًا للحذف أولاً.")
                return

            rows = sorted({item.row() for item in selected}, reverse=True)
            for row in rows:
                if 0 <= row < len(self._current_items):
                    name = self._current_items[row].get("name", "?")
                    del self._current_items[row]

            self._refresh_table()
            self._compute_totals()
            QMessageBox.information(self, "تم الحذف", f"تم حذف {len(rows)} بند.")
        except RuntimeError:
            pass

    def _compute_totals(self):
        """حساب وإظهار الإجماليات."""
        try:
            items = self._current_items
            if not items:
                self.lbl_base_cost.setText("التكلفة الأساسية: 0 ر.س")
                self.lbl_overhead.setText("0 ر.س")
                self.lbl_contingency.setText("0 ر.س")
                self.lbl_profit.setText("0 ر.س")
                self.lbl_discount.setText("0 ر.س")
                self.lbl_net_before_vat.setText("0 ر.س")
                self.lbl_vat.setText("0 ر.س")
                self.lbl_grand_total.setText("0 ر.س")
                return

            totals = compute_quote_totals(items)

            self.lbl_base_cost.setText(f"التكلفة الأساسية: {totals['base_cost']:,.2f} ر.س")
            self.lbl_overhead.setText(f"{totals['overhead']:,.2f} ر.س")
            self.lbl_contingency.setText(f"{totals['contingency']:,.2f} ر.س")
            self.lbl_profit.setText(f"{totals['profit']:,.2f} ر.س")
            self.lbl_discount.setText(f"{totals['discount']:,.2f} ر.س")
            self.lbl_net_before_vat.setText(f"{totals['net_before_vat']:,.2f} ر.س")
            self.lbl_vat.setText(f"{totals['vat']:,.2f} ر.س")
            self.lbl_grand_total.setText(f"{totals['grand_total']:,.2f} ر.س")
        except RuntimeError:
            pass

    def _new_quote(self):
        """بدء عرض جديد من الصفر."""
        try:
            self._current_items.clear()
            self._refresh_table()
            self.quote_no_edit.setText(generate_quote_number())
            self.project_name_edit.clear()
            self.location_edit.clear()
            self.area_spin.setValue(0)
            self.floors_spin.setValue(0)
            self._compute_totals()
            QMessageBox.information(self, "عرض جديد", "تم بدء عرض سعر جديد.")
        except RuntimeError:
            pass

    def _export_csv(self):
        """تصدير العرض الحالي كملف CSV."""
        if not self._current_items:
            QMessageBox.information(self, "لا يوجد عرض", "أضف بنودًا قبل التصدير.")
            return

        quote_no = self.quote_no_edit.text() or "draft"
        project_name = self.project_name_edit.text() or "مشروع"
        client_name = self._current_client_name or "غير محدد"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "تصدير العرض كـ CSV",
            f"quote-{quote_no.replace('/', '-')}.csv",
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write("عرض سعر,محمّد الحيلة\n")
                f.write(f"رقم العرض,{quote_no}\n")
                f.write(f"العميل,{client_name}\n")
                f.write(f"المشروع,{project_name}\n")
                f.write(f"الموقع,{self.location_edit.text() or '-'}\n")
                f.write(f"التاريخ,{self.date_edit.date().toString('yyyy-MM-dd')}\n")
                f.write(f"المساحة,{self.area_spin.value():,.0f} م²\\n")
                f.write(f"الطوابق,{self.floors_spin.value()}\\n")
                f.write("\n")
                f.write("الرمز,الاسم,الكمية,الوحدة,س.الشراء,س.التثبيت,الإجمالي\n")
                for item in self._current_items:
                    f.write(
                        f"{item.get('code','')},{item.get('name','')},"
                        f"{item.get('qty',0)},{item.get('unit','')},"
                        f"{item.get('supply_price_sar',0):,.0f},"
                        f"{item.get('install_price_sar',0):,.0f},"
                        f"{item.get('total',0):,.0f}\n"
                    )
                f.write("\n")
                totals = compute_quote_totals(self._current_items)
                f.write(f"التكلفة الأساسية,{totals['base_cost']:,.2f}\n")
                f.write(f"النفقات العامة (8%),{totals['overhead']:,.2f}\n")
                f.write(f"هامش الطوارئ (5%),{totals['contingency']:,.2f}\n")
                f.write(f"هامش الربح (15%),{totals['profit']:,.2f}\n")
                f.write(f"السعر قبل الضريبة,{totals['net_before_vat']:,.2f}\n")
                f.write(f"ضريبة القيمة المضافة (15%),{totals['vat']:,.2f}\n")
                f.write(f"الخصم,{totals['discount']:,.2f}\n")
                f.write(f"الإجمالي النهائي,{totals['grand_total']:,.2f}\n")

            QMessageBox.information(
                self,
                "تم التصدير",
                f"تم حفظ العرض في:\n{path}",
            )
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"تعذّر حفظ الملف:\n{e}")

    # ── واجهة خارجية لـ app.py ──────────────────────────────────

    def refresh(self):
        """يُستدعى عند التبديل للتبويب — يحمل قائمة العملاء."""
        try:
            from database import Client
            session = None
            try:
                from database import get_session
                session = get_session()
                clients = session.query(Client).order_by(Client.name).limit(200).all()
                self.client_combo.clear()
                self.client_combo.addItem("اختر عميل")
                for c in clients:
                    self.client_combo.addItem(f"{c.name} ({c.city or ''})", userData=c.id)
                self.quote_no_edit.setText(self.quote_no_edit.text() or generate_quote_number())
            finally:
                if session:
                    session.close()
        except RuntimeError:
            pass

    def get_current_quote(self) -> dict:
        """إرجاع عرض الحالي كـ dict جاهز للتخزين أو التصدير."""
        project_name = self.project_name_edit.text().strip()
        quote_no = self.quote_no_edit.text().strip() or generate_quote_number()

        return {
            "quote_no": quote_no,
            "client_id": self._client_id,
            "client_name": self._current_client_name,
            "name": project_name or "عرض سعر",
            "location": self.location_edit.text().strip(),
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "area": self.area_spin.value(),
            "floors": self.floors_spin.value(),
            "currency": "SAR",
            "vat": 15,
            "validity": 30,
            "status": "draft",
            "notes": "",
            "items": self._current_items,
        }
