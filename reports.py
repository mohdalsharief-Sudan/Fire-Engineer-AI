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

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
ARABIC_FONT_PATH = os.path.join(FONTS_DIR, "Arabic.ttf")

_ARABIC_FONT_NAME = "Helvetica"
if os.path.exists(ARABIC_FONT_PATH):
    try:
        pdfmetrics.registerFont(TTFont("ArabicFont", ARABIC_FONT_PATH))
        _ARABIC_FONT_NAME = "ArabicFont"
    except Exception:
        pass

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
    styles.add(ParagraphStyle(
        name="ReportTitle", fontSize=20, leading=24, textColor=DARK,
        spaceAfter=4, fontName=_ARABIC_FONT_NAME
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle", fontSize=11, textColor=MUTED, spaceAfter=14,
        fontName=_ARABIC_FONT_NAME
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader", fontSize=13, textColor=ACCENT,
        fontName=_ARABIC_FONT_NAME, spaceBefore=14, spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name="BodyMuted", fontSize=10, textColor=MUTED, fontName=_ARABIC_FONT_NAME
    ))
    return styles


def _kv_table(pairs, col_widths=(45 * mm, 120 * mm)):
    normal = getSampleStyleSheet()["Normal"]
    normal.fontName = _ARABIC_FONT_NAME
    rows = [[Paragraph(f"<b>{ar(k)}</b>", normal), Paragraph(ar(v) if v else "-", normal)] for k, v in pairs]
    t = Table(rows, colWidths=list(col_widths))
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
        ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
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

    story.append(Paragraph(company_name, styles["ReportSubtitle"]))
    story.append(Paragraph(f"Project Report — {project.name}", styles["ReportTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT))
    story.append(Spacer(1, 10))

    # Project info
    story.append(Paragraph(ar("معلومات المشروع"), styles["SectionHeader"]))
    story.append(_kv_table([
        (ar("رقم المشروع"), str(project.id)),
        (ar("العميل"), project.client_name),
        (ar("الموقع"), project.site),
        (ar("المبنى"), project.building),
        (ar("نطاق النظام"), project.scope),
        (ar("المعيار المرجعي"), project.standard),
        (ar("الحالة"), project.status),
        (ar("تاريخ البدء"), str(project.start_date) if project.start_date else "-"),
        (ar("تاريخ الانتهاء"), str(project.end_date) if project.end_date else "-"),
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
            (ar("اسم العميل"), c.name),
            (ar("مسؤول التواصل"), c.contact_person),
            (ar("الهاتف"), c.phone),
            (ar("البريد الإلكتروني"), c.email),
            (ar("العنوان"), c.address),
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
