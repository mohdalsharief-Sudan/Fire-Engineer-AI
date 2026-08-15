"""
reports.py
توليد تقارير PDF احترافية للمشاريع باستخدام reportlab.
يتطلب: pip install reportlab
"""

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ACCENT = colors.HexColor("#e8543a")
DARK = colors.HexColor("#1a2029")
MUTED = colors.HexColor("#8b97a8")

# ---------------------------------------------------------------------------
# دعم اللغة العربية في PDF
#
# reportlab لا يدعم تشكيل/اتجاه النص العربي افتراضيًا. لتفعيل ذلك بشكل صحيح:
#   1) pip install arabic-reshaper python-bidi
#   2) ضع خطًا عربيًا (مثل Amiri أو Noto Naskh Arabic) بصيغة .ttf داخل مجلد
#      fonts/ بجانب هذا الملف باسم "Arabic.ttf"
# إن لم تتوفر هذه المتطلبات، سيتم عرض النص العربي كما هو (قد يظهر غير متصل
# الحروف أو بالاتجاه الخاطئ) بدون أن يتوقف البرنامج عن العمل.
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(_BASE_DIR, "fonts")


def _discover_arabic_fonts():
    """
    يبحث عن خط عربي في عدة أماكن محتملة بدل مسار واحد صارم.
    يعيد (regular_path, bold_path) وقد يكون أي منهما None.

    ترتيب البحث:
      1) fonts/Arabic.ttf   (المسار الموصى به)
      2) fonts/*.ttf        (أي خط تضعه في المجلد)
      3) بجانب الملفات مباشرة: NotoNaskhArabic*.ttf أو Amiri*.ttf
      4) static/*.ttf       (كما تأتي حزمة Google Fonts)
    """
    candidates = [
        os.path.join(FONTS_DIR, "Arabic.ttf"),
    ]
    search_dirs = [FONTS_DIR, _BASE_DIR, os.path.join(_BASE_DIR, "static")]
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            low = fname.lower()
            if not low.endswith(".ttf"):
                continue
            if "bold" in low:
                continue  # الغامق يُختار لاحقًا
            if low.startswith("arabic") or "naskh" in low or "amiri" in low \
                    or "cairo" in low or "tajawal" in low:
                candidates.append(os.path.join(d, fname))

    regular = next((p for p in candidates if os.path.exists(p)), None)

    bold = None
    bold_candidates = [os.path.join(FONTS_DIR, "Arabic-Bold.ttf")]
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            low = fname.lower()
            if low.endswith(".ttf") and "bold" in low:
                bold_candidates.append(os.path.join(d, fname))
    bold = next((p for p in bold_candidates if os.path.exists(p)), None)

    return regular, bold


ARABIC_FONT_PATH, ARABIC_BOLD_PATH = _discover_arabic_fonts()

_ARABIC_FONT_NAME = "Helvetica"
_ARABIC_BOLD_NAME = "Helvetica-Bold"

if ARABIC_FONT_PATH:
    try:
        pdfmetrics.registerFont(TTFont("ArabicFont", ARABIC_FONT_PATH))
        _ARABIC_FONT_NAME = "ArabicFont"
        _ARABIC_BOLD_NAME = "ArabicFont"  # افتراضيًا نفس الخط

        if ARABIC_BOLD_PATH:
            try:
                pdfmetrics.registerFont(TTFont("ArabicFont-Bold", ARABIC_BOLD_PATH))
                _ARABIC_BOLD_NAME = "ArabicFont-Bold"
            except Exception:
                pass

        # تسجيل عائلة الخط حتى تعمل وسوم <b> داخل Paragraph بشكل صحيح
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        registerFontFamily(
            "ArabicFont",
            normal="ArabicFont",
            bold=_ARABIC_BOLD_NAME,
            italic="ArabicFont",
            boldItalic=_ARABIC_BOLD_NAME,
        )
    except Exception as _e:
        print("تحذير: تعذر تحميل الخط العربي:", _e)
else:
    print(
        "تحذير: لم يُعثر على خط عربي (.ttf). ستظهر النصوص العربية في ملفات PDF\n"
        f"        بشكل غير صحيح. ضع خطًا عربيًا هنا: {os.path.join(FONTS_DIR, 'Arabic.ttf')}"
    )

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _HAS_ARABIC_SHAPING = True
except ImportError:
    _HAS_ARABIC_SHAPING = False


def ar(text):
    """يعيد تشكيل النص العربي للعرض الصحيح إن كانت المكتبات متوفرة، وإلا يعيده كما هو."""
    if not text:
        return text
    if _HAS_ARABIC_SHAPING:
        try:
            reshaped = arabic_reshaper.reshape(str(text))
            return get_display(reshaped)
        except Exception:
            return str(text)
    return str(text)


def _styles():
    styles = getSampleStyleSheet()
    for name in ("Normal", "BodyText"):
        styles[name].fontName = _ARABIC_FONT_NAME
        styles[name].alignment = TA_RIGHT
    styles.add(ParagraphStyle(
        name="ReportTitle", fontSize=20, leading=24, textColor=DARK,
        spaceAfter=4, fontName=_ARABIC_FONT_NAME, alignment=TA_RIGHT
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle", fontSize=11, textColor=MUTED, spaceAfter=14,
        fontName=_ARABIC_FONT_NAME, alignment=TA_RIGHT
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader", fontSize=13, textColor=ACCENT,
        fontName=_ARABIC_FONT_NAME, spaceBefore=14, spaceAfter=6,
        alignment=TA_RIGHT
    ))
    styles.add(ParagraphStyle(
        name="BodyMuted", fontSize=10, textColor=MUTED,
        fontName=_ARABIC_FONT_NAME, alignment=TA_RIGHT
    ))
    return styles


def _kv_table(pairs, col_widths=(45 * mm, 120 * mm)):
    # نستخدم نمطًا مستقلًا بدل تعديل getSampleStyleSheet()["Normal"] العام
    # (التعديل العام كان يسرّب إعدادات الخط لبقية التقرير)
    cell = ParagraphStyle(
        name="KVCell", fontName=_ARABIC_FONT_NAME, fontSize=10,
        leading=14, alignment=TA_RIGHT, textColor=DARK
    )
    # ملاحظة: لا نستخدم وسم <b> هنا. عند لفّ نص عربي مُعالَج بـ bidi داخل <b>
    # يعيد reportlab ترتيب المقاطع فيظهر النص معكوسًا ("رقم المشروع" -> "عورشملا مقر").
    # الحل: نمط منفصل بخط غامق بدل الوسم.
    cell_bold = ParagraphStyle(
        name="KVCellBold", parent=cell, fontName=_ARABIC_BOLD_NAME
    )
    rows = [[Paragraph(ar(k), cell_bold), Paragraph(ar(v) if v else "-", cell)]
            for k, v in pairs]
    # في المستند العربي يأتي عمود التسمية على اليمين
    t = Table(rows, colWidths=list(col_widths))
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
        ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
    ]))
    return t


def generate_project_report_pdf(project, path, company_name="Fire Protection Engineering"):
    """
    project: كائن Project (مع علاقات client / invoices / equipment محمّلة)
    path: مسار ملف الـ PDF الناتج
    """
    styles = _styles()
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm
    )
    story = []

    story.append(Paragraph(ar(company_name), styles["ReportSubtitle"]))
    # كان اسم المشروع يُطبع بدون ar() فيظهر بحروف مقطّعة إن كان عربيًا
    story.append(Paragraph(ar(f"تقرير مشروع — {project.name}"), styles["ReportTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT))
    story.append(Spacer(1, 10))

    # Project info
    story.append(Paragraph(ar("معلومات المشروع"), styles["SectionHeader"]))
    story.append(_kv_table([
        ("رقم المشروع", str(project.id)),
        ("العميل", project.client_name),
        ("الموقع", project.site),
        ("المبنى", project.building),
        ("نطاق النظام", project.scope),
        ("المعيار المرجعي", project.standard),
        ("الحالة", project.status),
        ("تاريخ البدء", str(project.start_date) if project.start_date else "-"),
        ("تاريخ الانتهاء", str(project.end_date) if project.end_date else "-"),
    ]))

    if project.notes:
        story.append(Spacer(1, 8))
        story.append(Paragraph(ar("ملاحظات:"), styles["BodyMuted"]))
        story.append(Paragraph(ar(project.notes).replace("\n", "<br/>"), styles["Normal"]))

    # Client info
    if project.client:
        c = project.client
        story.append(Paragraph(ar("بيانات العميل"), styles["SectionHeader"]))
        story.append(_kv_table([
            ("اسم العميل", c.name),
            ("مسؤول التواصل", c.contact_person),
            ("الهاتف", c.phone),
            ("البريد الإلكتروني", c.email),
            ("العنوان", c.address),
        ]))

    # Equipment
    if project.equipment:
        story.append(Paragraph(ar("المعدات والفحص الدوري"), styles["SectionHeader"]))
        header = [ar(h) for h in ["المعدة", "النوع", "الموقع", "آخر فحص", "الفحص القادم", "الحالة"]]
        rows = [header]
        for e in project.equipment:
            rows.append([
                ar(e.name) or "-", ar(e.equipment_type) or "-", ar(e.location) or "-",
                str(e.last_inspection_date) if e.last_inspection_date else "-",
                str(e.next_inspection_date) if e.next_inspection_date else "-",
                ar(e.status) or "-",
            ])
        t = Table(rows, colWidths=[32 * mm, 28 * mm, 28 * mm, 24 * mm, 28 * mm, 25 * mm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)

    # Invoices
    if project.invoices:
        story.append(Paragraph(ar("الفواتير"), styles["SectionHeader"]))
        header = [ar(h) for h in ["رقم الفاتورة", "المبلغ", "تاريخ الإصدار", "تاريخ الاستحقاق", "الحالة"]]
        rows = [header]
        for i in project.invoices:
            rows.append([
                i.invoice_number or f"#{i.id}",
                f"{i.amount:,.2f}" if i.amount else "0.00",
                str(i.issue_date) if i.issue_date else "-",
                str(i.due_date) if i.due_date else "-",
                ar(i.status) or "-",
            ])
        t = Table(rows, colWidths=[32 * mm, 30 * mm, 32 * mm, 32 * mm, 25 * mm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))
        total = sum(i.amount or 0 for i in project.invoices)
        unpaid = sum(i.amount or 0 for i in project.invoices if i.status != "Paid")
        story.append(Paragraph(
            ar(f"إجمالي الفواتير: {total:,.2f} — غير المسدد: {unpaid:,.2f}"), styles["BodyMuted"]
        ))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
    story.append(Paragraph(ar("تم إنشاء هذا التقرير آليًا بواسطة FireEngineerAI"), styles["BodyMuted"]))

    doc.build(story)
    return path
