"""
cad_tool_tab.py
───────────────
تبويب "تحليل CAD" — يجرّب ملف DXF ويعرض نتائج تحليل أنظمة الحماية من الحريق.
يستخدم ezdxf لمطابقة ما يفعله dxf_report.py لكن بواجهة داخل FireEngineerAI.
المهندس يحدد الملف يدوياً (لا CAD auto-read).
"""


import os
import collections
try:
    import ezdxf
    from ezdxf import bbox
    EZDXF_AVAILABLE = True
except ImportError:
    ezdxf = None
    bbox = None
    EZDXF_AVAILABLE = False

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QTextEdit, QLabel, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSplitter, QSizePolicy,
    QFormLayout, QSpinBox, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
# ────────────────────────────────────────────────────────────────
# CadAnalyzeThread — يحلّل ملف DXF في خلفية (QThread)
# حتى لا يتجمّد الواجهة أثناء قراءة الملف ومعالجته
# ────────────────────────────────────────────────────────────────
class CadAnalyzeThread(QThread):
    """ينفذ تحليل DXF في خيط خلفي ويعيد النتائج عبر Signals."""

    result_ready = Signal(str, dict, list)
    error_occurred = Signal(str)

    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self._filepath = filepath

    def run(self):
        try:
            doc = ezdxf.readfile(self._filepath)
            msp = doc.modelspace()
            out = []

            def _p(*a):
                out.append(" ".join(str(x) for x in a))

            # ---- 1) هندسة المواسير (P-PIPE) ----
            lines = [e for e in msp
                     if e.dxftype() == "LINE" and e.dxf.layer == "P-PIPE"]
            total_len = sum((e.dxf.end - e.dxf.start).magnitude for e in lines)
            _p(f"P-PIPE LINE: count={len(lines)} "
               f"total={total_len / 1000:.1f} m")

            len_dist = collections.Counter()
            for e in lines:
                l = (e.dxf.end - e.dxf.start).magnitude
                if l < 100:
                    len_dist["<100mm"] += 1
                elif l < 500:
                    len_dist["<500mm"] += 1
                elif l < 2000:
                    len_dist["<2m"] += 1
                elif l < 10000:
                    len_dist["<10m"] += 1
                else:
                    len_dist[">=10m"] += 1
            _p("  توزيع الأطوال:", dict(len_dist))

            arcs = [e for e in msp
                    if e.dxftype() == "ARC" and e.dxf.layer == "P-PIPE"]
            arc_len = sum(
                e.dxf.radius * __import__('math').radians(
                    (e.dxf.end_angle - e.dxf.start_angle) % 360 or 360
                )
                for e in arcs
            )
            _p(f"P-PIPE ARC: count={len(arcs)} "
               f"total={arc_len / 1000:.1f} m")

            pipe_inserts = collections.Counter(
                e.dxf.name for e in msp
                if e.dxftype() == "INSERT" and e.dxf.layer == "P-PIPE"
            )
            _p("P-PIPE INSERT (أكثر 15):",
               dict(pipe_inserts.most_common(15)))

            _p("\n== ELLIPSE على P-PIPE: "
               "(القطر الرئيسي مم، النسبة) : العدد")
            ellipses = collections.Counter(
                (round(e.dxf.major_axis.magnitude * 2), round(e.dxf.ratio, 2))
                for e in msp
                if e.dxftype() == "ELLIPSE"
                and e.dxf.layer == "P-PIPE"
            )
            for k, v in ellipses.most_common(20):
                _p(f"{v:5}  {k}")

            texts = [e for e in msp
                     if e.dxftype() == "MTEXT"
                     and e.dxf.layer == "P-PIPE-IDEN"]
            _p("\n== نصوص P-PIPE-IDEN (أكثر 30):")
            for k, v in collections.Counter(
                self._plain_text(e) for e in texts
            ).most_common(30):
                _p(f"{v:5}  {k!r}")

            KEY = __import__('re').compile(
                r"Fire Fighting|CO2|FHC|EXTINGUISHER|Fire-Hose",
                __import__('re').I
            )
            _p("\n== البلوكات المهمة: layer | name | position | "
               "attribs | محتوى البلوك | الحجم")

            fire_blocks = []
            n = 0
            for e in msp:
                if e.dxftype() != "INSERT" or not KEY.search(e.dxf.name):
                    continue
                blk = doc.blocks.get(e.dxf.name)
                if blk is None:
                    continue
                content = collections.Counter(
                    (x.dxftype(), x.dxf.layer) for x in blk
                )
                try:
                    box = bbox.extents(blk, fast=True)
                    size = (f"{box.size.x:.0f}x{box.size.y:.0f}"
                            if box.has_data else "-")
                except Exception:
                    size = "?"
                attrs = {a.dxf.tag: a.dxf.text for a in e.attribs}
                pos = tuple(round(v) for v in e.dxf.insert)
                _p(f"{e.dxf.layer} | {e.dxf.name[:70]} | {pos} | "
                   f"{attrs} | {dict(content)} | {size}")
                fire_blocks.append({
                    "layer": e.dxf.layer,
                    "name": e.dxf.name[:70],
                    "position": str(pos),
                    "size": size,
                    "content": str(dict(content)),
                })
                n += 1
                if n >= 80:
                    break

            result = "\n".join(out)
            stats = {
                "lines": len(lines),
                "arcs": len(arcs),
                "ellipses": len(ellipses),
                "fire_blocks": len(fire_blocks),
            }
            self.result_ready.emit(result, stats, fire_blocks)

        except Exception as exc:
            self.error_occurred.emit(f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _plain_text(entity):
        try:
            return entity.plain_text().strip()
        except Exception:
            return str(getattr(entity, "text", "")).strip()




class CadToolTab(QWidget):
    """
    تبويب تحليل ملفات CAD (DXF) لأنظمة الحماية من الحرائق.
    يُضاف إلى FireEngineerAI كصفحة داخل QStackedWidget.
    
    المهندس يحدد الملف يدوياً — لا تحميل تلقائي.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_path = ""
        self._last_result = ""
        self._status_callback = None
        self.setup_ui()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── العنوان ──
        title = QLabel("تحليل CAD" if EZDXF_AVAILABLE else "تحليل CAD (غير متوفر)")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        sub = QLabel(
            "تحليل ملفات AutoCAD (DXF) لأنظمة الحماية من الحرائق يدوياً. "
            "تحديد الملف → عرض النتائج والتقارير."
        )
        sub.setObjectName("PageSubtitle")
        root.addWidget(sub)

        # ── زر اختيار الملف ──
        top_row = QHBoxLayout()
        self.btn_open = QPushButton("📂開ير ملف DXF")
        self.btn_open.setObjectName("PrimaryButton")
        self.btn_open.setFixedWidth(160)
        self.btn_open.clicked.connect(self._open_file)
        top_row.addWidget(self.btn_open)

        self.lbl_path = QLabel("(لم يتم اختيار ملف بعد)")
        self.lbl_path.setObjectName("StatValue")
        top_row.addWidget(self.lbl_path)
        top_row.addStretch()

        self.btn_analyze = QPushButton("🔍 تحليل الملف")
        self.btn_analyze.setObjectName("PrimaryButton")
        self.btn_analyze.setFixedWidth(140)
        self.btn_analyze.clicked.connect(self._analyze)
        top_row.addWidget(self.btn_analyze)

        self.btn_export = QPushButton("📋 نسخ النتائج")
        self.btn_export.setFixedWidth(130)
        self.btn_export.clicked.connect(self._copy_results)
        top_row.addWidget(self.btn_export)

        root.addLayout(top_row)

        # ─– ملخص سريع ──
        summary_card, summary_lay = self._make_card("الملخص السريع")

        self.lbl_lines = QLabel("الخطوط (P-PIPE): 0")
        summary_lay.addWidget(self.lbl_lines)

        self.lbl_arcs = QLabel("القوسات (P-PIPE): 0")
        summary_lay.addWidget(self.lbl_arcs)

        self.lbl_inserts = QLabel("البلوكات المهمة: 0")
        summary_lay.addWidget(self.lbl_inserts)

        self.lbl_ellipses = QLabel("نهايات المواسير (ELLIPSE): 0")
        summary_lay.addWidget(self.lbl_ellipses)

        root.addLayout(summary_lay)

        # ─– نتائج التحليل (منقسمة) ──
        splitter = QSplitter(Qt.Vertical)
        splitter.setSizes([400, 300])

        # النتائج الكاملة
        result_card, result_lay = self._make_card("تفاصيل التحليل")
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText(
            "سيظهر هنا تحليل الملف بعد الضغط على «تحليل الملف»...\n\n"
            "مثال:\n"
            "  P-PIPE LINE: count=47 total=124.5 m\n"
            "  P-PIPE ARC: count=12 total=38.2 m\n"
            "  == البلوكات المهمة: ...\n"
        )
        self.result_text.document().setDefaultFont(
            QFont("Tahoma", 11)
        )
        result_lay.addWidget(self.result_text)
        splitter.addWidget(result_card)

        # جدول البلوكات
        blocks_card, blocks_lay = self._make_card("البلوكات المهمة (نقاط الحريق)")
        self.blocks_table = QTableWidget(0, 5)
        self.blocks_table.setHorizontalHeaderLabels([
            "الطبقة", "الاسم", "الموقع (X,Y)", "الحجم", "المحتوى"
        ])
        self.blocks_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.blocks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.blocks_table.verticalHeader().setVisible(False)

        hdr = self.blocks_table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)

        self.blocks_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e2e;
                alternate-background-color: #252536;
                gridline-color: #3a3a4a;
                border: 1px solid #3a3a4a;
                border-radius: 8px;
                font-size: 12px;
            }
            QTableWidget::item:selected {
                background-color: #3b4a6b;
            }
            QHeaderView::section {
                background-color: #0f1626;
                color: #3498DB;
                padding: 6px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid #3a3a4a;
            }
        """)

        blocks_lay.addWidget(self.blocks_table)
        splitter.addWidget(blocks_card)

        root.addWidget(splitter)

        # ─– تحليل يدوي ──
        manual_card, manual_lay = self._make_card("تحليل يدوي (كميات من قياس شخصي)")
        form = QFormLayout()
        form.setSpacing(6)

        self.qty_extinguisher_sb = QSpinBox()
        self.qty_extinguisher_sb.setRange(0, 99999)
        self.qty_extinguisher_sb.setValue(0)
        form.addRow("عدد طفايات الحريق:", self.qty_extinguisher_sb)

        self.qty_hose_reel_sb = QSpinBox()
        self.qty_hose_reel_sb.setRange(0, 99999)
        self.qty_hose_reel_sb.setValue(0)
        form.addRow("عدد حبال الإطفاء (Hose Reel):", self.qty_hose_reel_sb)

        self.qty_alarm_point_sb = QSpinBox()
        self.qty_alarm_point_sb.setRange(0, 99999)
        self.qty_alarm_point_sb.setValue(0)
        form.addRow("نقاط الإنذار:", self.qty_alarm_point_sb)

        self.qty_hydrant_sb = QSpinBox()
        self.qty_hydrant_sb.setRange(0, 99999)
        self.qty_hydrant_sb.setValue(0)
        form.addRow("نقاط الحنطرة (Hydrant):", self.qty_hydrant_sb)

        self.qty_sprinkler_sb = QSpinBox()
        self.qty_sprinkler_sb.setRange(0, 99999)
        self.qty_sprinkler_sb.setValue(0)
        form.addRow("رؤوس الرشاشات (Sprinkler Head):", self.qty_sprinkler_sb)

        self.btn_manual_analyze = QPushButton("📊 حساب التحليل اليدوي")
        self.btn_manual_analyze.setObjectName("SecondaryButton")
        self.btn_manual_analyze.setFixedWidth(220)
        self.btn_manual_analyze.clicked.connect(self._manual_analyze)

        form.addRow(self.btn_manual_analyze)
        manual_lay.addLayout(form)
        root.addLayout(manual_lay)

        root.addStretch()

    # ── المساعدة ─────────────────────────────────────────────────

    def _make_card(self, title=None):
        """بطاقة مشابهة لـ make_card في app.py."""
        card = QGroupBox(title or "")
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        return card, layout

    def _open_file(self):
        """فتح ملف DXF."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "اختيار ملف DXF",
            self._last_path or "",
            "ملفات DXF (*.dxf);;جميع الملفات (*)",
        )
        if not path:
            return
        self._last_path = path
        name = os.path.basename(path)
        self.lbl_path.setText(f"📄 {name}")
        self.result_text.setPlainText(f"✅ تم اختيار: {name}\nالآن اضغط «تحليل الملف» لبدء التحليل.")

    def _analyze(self):
        """تشغيل التحليل على الملف المحدد — threaded لمنع تجميد الواجهة."""
        path = self._last_path
        if not EZDXF_AVAILABLE:
            self.result_text.setPlainText(
                "⚠️ مكتبة التحليل (ezdxf) غير متاحة.\n\n"
                "الحل: تشغيل الأمر التالي في الطرفية:\n"
                "   pip install ezdxf\n\n"
                "أو يمكن للمهندس تحليل الملف يدوياً باستخدام أدوات أخرى."
            )
            return

        if not path or not os.path.exists(path):
            self.result_text.setPlainText("⚠️ لم تختر ملفًا بعد. اضغط «اختيار ملف DXF» أولاً.")
            return

        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("⏳ جاري التحليل...")
        self.result_text.setPlainText(f"⏳ جاري تحليل: {os.path.basename(path)}...")
        self._analysis_thread = CadAnalyzeThread(path)
        self._analysis_thread.result_ready.connect(self._on_analysis_finished)
        self._analysis_thread.error_occurred.connect(self._on_analysis_error)
        self._analysis_thread.start()

    def _on_analysis_finished(self, result_str, stats_dict, blocks_list):
        """يُستدعى عند اكتمال التحليل من الخيط الخلفي."""
        # فحص: هل الـ widget لا يزال مرئيًا؟
        if not self.isVisible():
            return
        try:
            self._last_result = result_str
            self.result_text.setPlainText(result_str)

            # تحديث الملخص
            self.lbl_lines.setText(f"الخطوط (P-PIPE): {stats_dict.get('lines', 0)}")
            self.lbl_arcs.setText(f"القوسات (P-PIPE): {stats_dict.get('arcs', 0)}")
            self.lbl_ellipses.setText(f"نهايات المواسير (ELLIPSE): {stats_dict.get('ellipses', 0)}")
            self.lbl_inserts.setText(f"البلوكات المهمة: {stats_dict.get('fire_blocks', 0)}")

            # ملء جدول البلوكات
            self.blocks_table.setRowCount(0)
            for blk in blocks_list:
                row = self.blocks_table.rowCount()
                self.blocks_table.insertRow(row)
                self.blocks_table.setItem(row, 0, QTableWidgetItem(str(blk.get("layer", ""))))
                self.blocks_table.setItem(row, 1, QTableWidgetItem(str(blk.get("name", ""))))
                self.blocks_table.setItem(row, 2, QTableWidgetItem(str(blk.get("position", ""))))
                self.blocks_table.setItem(row, 3, QTableWidgetItem(str(blk.get("size", ""))))
                self.blocks_table.setItem(row, 4, QTableWidgetItem(str(blk.get("content", ""))))
            if self._status_callback:
                self._status_callback(
                    f"تم التحليل: {stats_dict.get('lines', 0)} خط، "
                    f"{stats_dict.get('fire_blocks', 0)} كتلة حريق"
                )
        except RuntimeError as e:
            # libshiboken: الـ widget تم تدميره — نتجاهل الصامت
            pass
        except Exception as exc:
            try:
                self.result_text.setPlainText(f"❌ خطأ في عرض النتائج: {exc}")
            except Exception:
                pass
        finally:
            try:
                self.btn_analyze.setEnabled(True)
                self.btn_analyze.setText("🔍 تحليل الملف")
            except Exception:
                pass

    def _on_analysis_error(self, msg):
        """يُستدعى عند خطأ في التحليل الخلفي."""
        if not self.isVisible():
            return
        try:
            self.result_text.setPlainText(f"❌ خطأ في التحليل:\n{msg}")
            self.lbl_lines.setText("الخطوط (P-PIPE): خطأ")
            self.lbl_arcs.setText("القوسات (P-PIPE): خطأ")
            self.lbl_ellipses.setText("نهايات المواسير: خطأ")
            self.lbl_inserts.setText("البلوكات: خطأ")
            if self._status_callback:
                self._status_callback(f"خطأ في التحليل: {msg}")
        except RuntimeError:
            pass
        except Exception:
            pass
        finally:
            try:
                self.btn_analyze.setEnabled(True)
                self.btn_analyze.setText("🔍 تحليل الملف")
            except Exception:
                pass

    def _plain_text(self, entity):
        """الحصول على نص المحتوى لمثيل DXF."""
        try:
            return entity.plain_text().strip()
        except Exception:
            return str(getattr(entity, "text", "")).strip()

    def _copy_results(self):
        """نسخ النتائج إلى الحافظة."""
        if not self._last_result:
            self.result_text.setPlainText("لا توجد نتائج للنسخ. قم بتحليل ملف أولاً.")
            return
        try:
            from PySide6.QtGui import QClipboard
            QClipboard().setText(self._last_result)
            self.result_text.append("\n\n✓ تم نسخ النتائج إلى الحافظة.")
        except Exception as e:
            self.result_text.append(f"\n\n✗ تعذّر نسخ النتائج: {e}")

    def refresh(self):
        """يُستدعى عند التبديل للتبويب — لا شيء خاص."""
        pass

    def _manual_analyze(self):
        """تحليل يدوي — الكميات التي يدخلها المهندس من قياسه الشخصي."""
        ext = self.qty_extinguisher_sb.value()
        hose = self.qty_hose_reel_sb.value()
        alarm = self.qty_alarm_point_sb.value()
        hydrant = self.qty_hydrant_sb.value()
        sprinkler = self.qty_sprinkler_sb.value()
        total_manual = ext + hose + alarm + hydrant + sprinkler

        lines = [
            "╔══════════════════════════════════════╗",
            "║     تحليل يدوي — الكميات المدخلة     ║",
            "╚══════════════════════════════════════╝",
            "",
            f"🔹  طفايات الحريق........ {ext}",
            f"🔹  حبال الإطفاء.......... {hose}",
            f"🔹  نقاط الإنذار......... {alarm}",
            f"🔹  نقاط الحنطرة......... {hydrant}",
            f"🔹  رؤوس الرشاشات........ {sprinkler}",
            "",
            f"📊  المجموع الكلي للعناصر: {total_manual}",
            "",
            "ملاحظة: استخدم هذا الجدول كمرجع في حسابات التكلفة.",
            "بعد الانتهاء — انقل الكميات إلى تبويب التسعير يدوياً.",
        ]

        self.result_text.clear()
        self.result_text.append("\n".join(lines))
        QMessageBox.information(
            self,
            "تحليل يدوي",
            f"تم تحديد {total_manual} عنصرًا يدوياً.\n"
            f"طفايات: {ext} | حبال: {hose} | إنذار: {alarm}\n"
            f"حنطرة: {hydrant} | رشاش: {sprinkler}",
        )
