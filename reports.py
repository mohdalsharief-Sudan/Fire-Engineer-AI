"""
reports.py
توليد تقارير PDF احترافية للمشاريع باستخدام reportlab.
يتطلب: pip install reportlab
"""

import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
)
from reportlab.lib.utils import ImageReader
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


def _load_company_settings():
    """
    يقرأ إعدادات المنشأة. الاستيراد داخل الدالة متعمَّد لتفادي دورة استيراد
    (settings يستورد database، وقد يُستورد reports قبلهما).
    """
    try:
        from settings import load_settings
        return load_settings()
    except Exception as e:
        print("تحذير: تعذر قراءة إعدادات المنشأة:", e)
        return {}


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
    styles.add(ParagraphStyle(
        name="Letterhead", fontSize=9, leading=13, textColor=DARK,
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


def _build_letterhead(cfg, styles):
    """
    يبني ترويسة التقرير من إعدادات المنشأة: الشعار على اليسار وبيانات
    الشركة على اليمين. إن لم يضبط المستخدم أي إعدادات تُعاد ترويسة فارغة
    ويظل التقرير سليمًا.
    """
    flow = []

    name_ar = (cfg.get("company_name") or "").strip()
    name_en = (cfg.get("company_name_en") or "").strip()

    # سطور التواصل: نعرض الموجود فقط بدل شرطات فارغة
    contact_bits = []
    if cfg.get("phone"):
        contact_bits.append(f"هاتف: {cfg['phone']}")
    if cfg.get("email"):
        contact_bits.append(cfg["email"])
    if cfg.get("website"):
        contact_bits.append(cfg["website"])

    reg_bits = []
    if cfg.get("cr_number"):
        reg_bits.append(f"س.ت: {cfg['cr_number']}")
    if cfg.get("vat_number"):
        reg_bits.append(f"الرقم الضريبي: {cfg['vat_number']}")

    info_lines = []
    if name_ar:
        info_lines.append(f'<font size="14">{ar(name_ar)}</font>')
    if name_en:
        info_lines.append(name_en)
    if cfg.get("address"):
        info_lines.append(ar(cfg["address"]))
    if contact_bits:
        info_lines.append(ar("  |  ".join(contact_bits)))
    if reg_bits:
        info_lines.append(ar("  |  ".join(reg_bits)))

    if not info_lines and not cfg.get("logo_path"):
        return flow

    info_para = Paragraph("<br/>".join(info_lines), styles["Letterhead"])

    logo_path = cfg.get("logo_path") or ""
    logo_flowable = ""
    if logo_path and os.path.exists(logo_path):
        try:
            # نحافظ على نسبة أبعاد الصورة داخل صندوق 32×32 مم
            reader = ImageReader(logo_path)
            iw, ih = reader.getSize()
            max_w, max_h = 32 * mm, 32 * mm
            scale = min(max_w / iw, max_h / ih)
            logo_flowable = Image(logo_path, width=iw * scale, height=ih * scale)
        except Exception as e:
            print("تحذير: تعذر تحميل شعار الشركة:", e)
            logo_flowable = ""

    # في التخطيط العربي: الشعار يسارًا والنص يمينًا
    head = Table([[logo_flowable, info_para]], colWidths=[35 * mm, 135 * mm])
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(head)
    flow.append(Spacer(1, 6))
    return flow


# ---------------------------------------------------------------------------
# أدوات مشتركة للتقارير المجمّعة
# ---------------------------------------------------------------------------

def _doc(path, landscape_mode=False):
    """مستند A4 بهوامش موحّدة. landscape للجداول العريضة."""
    size = landscape(A4) if landscape_mode else A4
    return SimpleDocTemplate(
        path, pagesize=size,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm
    )


def _cell(text, bold=False, align=TA_CENTER, color=None):
    """
    خلية جدول كـ Paragraph حتى يلتفّ النص الطويل داخل العمود.
    النص الخام في Table لا يلتفّ، فكان يتجاوز حدود الخلية ويتداخل
    مع العمود المجاور (مثل "Combined (Alarm + Sprinklers)").
    """
    st = ParagraphStyle(
        name="cell_b" if bold else "cell",
        fontName=_ARABIC_BOLD_NAME if bold else _ARABIC_FONT_NAME,
        fontSize=8.5, leading=11, alignment=align,
        textColor=color if color is not None else DARK,
    )
    return Paragraph(str(text), st)


def _data_table(header, rows, col_widths, align_right_cols=()):
    """
    جدول بيانات بنمط موحّد (رأس داكن، صفوف متناوبة).
    header/rows: نصوص جاهزة (مرّرها عبر ar() قبل الاستدعاء عند الحاجة).
    """
    hdr = [_cell(h, bold=True, color=colors.white) for h in header]
    body = []
    for r in rows:
        body.append([
            # الخلايا المبنية مسبقًا (مثل صف الإجمالي العريض) تُمرَّر كما هي
            v if isinstance(v, Paragraph)
            else _cell(v, align=TA_RIGHT if i in align_right_cols else TA_CENTER)
            for i, v in enumerate(r)
        ])
    data = [hdr] + body
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
        ("FONTNAME", (0, 0), (-1, 0), _ARABIC_BOLD_NAME),
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
    ]
    t.setStyle(TableStyle(style))
    return t


def _report_head(story, styles, cfg, title, subtitle=""):
    """ترويسة المنشأة + عنوان التقرير + تاريخ الإصدار."""
    story.extend(_build_letterhead(cfg, styles))
    story.append(Paragraph(ar(title), styles["ReportTitle"]))
    if subtitle:
        story.append(Paragraph(ar(subtitle), styles["ReportSubtitle"]))
    story.append(Paragraph(
        ar(f"تاريخ إصدار التقرير: {date.today().isoformat()}"), styles["BodyMuted"]
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT))
    story.append(Spacer(1, 10))


def _report_foot(story, styles, cfg):
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
    footer = (cfg.get("report_footer") or "").strip() \
        or "تم إنشاء هذا التقرير آليًا بواسطة FireEngineerAI"
    story.append(Paragraph(ar(footer), styles["BodyMuted"]))
    # رقم الإصدار في التذييل: يسهّل معرفة أي نسخة أنتجت تقريرًا قديمًا
    try:
        from applog import __version__ as _v
        story.append(Paragraph(ar(f"FireEngineerAI الإصدار {_v}"),
                               styles["BodyMuted"]))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# تقرير الفحوصات الدورية (للدفاع المدني / متابعة الصيانة)
# ---------------------------------------------------------------------------

def generate_contracts_report_pdf(contracts, path, settings=None,
                                  title="كشف عقود الصيانة السنوية"):
    """كشف بكل عقود الصيانة مع حالة السريان والزيارات والقيم المالية."""
    cfg = dict(settings) if settings else _load_company_settings()
    styles = _styles()
    doc = _doc(path, landscape_mode=True)
    story = []
    cur = cfg.get("currency") or "ريال"

    total_value = sum(c.value or 0 for c in contracts)
    active = [c for c in contracts if c.is_active]
    expired = [c for c in contracts if c.alert_level == "expired"]
    soon = [c for c in contracts if c.alert_level == "soon"]

    subtitle = (f"إجمالي العقود: {len(contracts)}  |  السارية: {len(active)}  |  "
                f"قريبة الانتهاء: {len(soon)}  |  منتهية: {len(expired)}  |  "
                f"إجمالي القيم: {total_value:,.2f} {cur}")
    _report_head(story, styles, cfg, title, subtitle)

    header = [ar(h) for h in [
        "م", "رقم العقد", "العنوان", "العميل", "الموقع/المشروع", "النطاق",
        "البدء", "الانتهاء", "المتبقي", "الزيارات", "القيمة", "الحالة",
    ]]

    rows = []
    for idx, c in enumerate(contracts, start=1):
        d = c.days_remaining
        if d is None:
            rem = "—"
        elif d < 0:
            rem = ar(f"منتهٍ ({abs(d)} يوم)")
        else:
            rem = ar(f"{d} يوم")

        status_ar = {"Active": "ساري", "Suspended": "موقوف",
                     "Cancelled": "ملغى"}.get(c.status, c.status or "—")

        rows.append([
            str(idx),
            ar(c.contract_number or "—"),
            ar(c.title or "—"),
            ar(c.client_name or "—"),
            ar(c.project_name or "كل المواقع"),
            ar(c.scope or "—"),
            str(c.start_date) if c.start_date else "—",
            str(c.end_date) if c.end_date else "—",
            rem,
            f"{c.visits_done}/{c.visits_per_year or 0}",
            f"{(c.value or 0):,.2f}",
            ar(status_ar),
        ])

    widths = [9 * mm, 24 * mm, 40 * mm, 36 * mm, 30 * mm, 26 * mm,
              20 * mm, 20 * mm, 24 * mm, 16 * mm, 24 * mm, 16 * mm]
    t = _data_table(header, rows, widths, align_right_cols=(10,))

    # تلوين عمود المتبقي حسب حالة السريان
    extra = []
    for i, c in enumerate(contracts, start=1):
        lvl = c.alert_level
        bg = {"expired": colors.HexColor("#f8d7da"),
              "soon": colors.HexColor("#fff3cd"),
              "unknown": colors.HexColor("#e9ecef"),
              "inactive": colors.HexColor("#e9ecef"),
              "none": colors.HexColor("#d4edda")}.get(lvl)
        if bg is not None:
            extra.append(("BACKGROUND", (8, i), (8, i), bg))
    if extra:
        t.setStyle(TableStyle(extra))
    story.append(t)

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(ar("الملخّص المالي"), styles["SectionHeader"]))
    paid = sum(c.total_invoiced - c.total_unpaid for c in contracts)
    unpaid = sum(c.total_unpaid for c in contracts)
    story.append(Paragraph(
        ar(f"إجمالي قيمة العقود: {total_value:,.2f} {cur}  |  "
           f"المفوتر: {sum(c.total_invoiced for c in contracts):,.2f} {cur}  |  "
           f"المحصّل: {paid:,.2f} {cur}  |  غير المسدَّد: {unpaid:,.2f} {cur}"),
        styles["Normal"]))

    _report_foot(story, styles, cfg)
    doc.build(story)
    return path


def generate_contract_certificate_pdf(contract, path, settings=None):
    """تقرير تفصيلي لعقد واحد يصلح للتسليم للعميل."""
    cfg = dict(settings) if settings else _load_company_settings()
    styles = _styles()
    doc = _doc(path)
    story = []
    cur = cfg.get("currency") or "ريال"
    c = contract

    heading = c.title or c.contract_number or f"عقد #{c.id}"
    _report_head(story, styles, cfg, "عقد صيانة سنوي", heading)

    status_ar = {"Active": "ساري", "Suspended": "موقوف",
                 "Cancelled": "ملغى"}.get(c.status, c.status or "—")
    d = c.days_remaining
    if d is None:
        rem = "—"
    elif d < 0:
        rem = f"منتهٍ منذ {abs(d)} يوم"
    else:
        rem = f"{d} يوم"

    story.append(Paragraph(ar("بيانات العقد"), styles["SectionHeader"]))
    story.append(_kv_table([
        ("رقم العقد", c.contract_number or "—"),
        ("العميل", c.client_name or "—"),
        ("الموقع/المشروع", c.project_name or "كل مواقع العميل"),
        ("نطاق الصيانة", c.scope or "—"),
        ("تاريخ البدء", str(c.start_date) if c.start_date else "—"),
        ("تاريخ الانتهاء", str(c.end_date) if c.end_date else "—"),
        ("المدة المتبقية", rem),
        ("الحالة", status_ar),
    ]))

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(ar("البنود المالية"), styles["SectionHeader"]))
    story.append(_kv_table([
        ("القيمة السنوية", f"{(c.value or 0):,.2f} {cur}"),
        ("دورة الدفع", c.payment_cycle or "—"),
        ("إجمالي المفوتر", f"{c.total_invoiced:,.2f} {cur}"),
        ("غير المسدَّد", f"{c.total_unpaid:,.2f} {cur}"),
    ]))

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(ar("الزيارات الدورية"), styles["SectionHeader"]))
    story.append(Paragraph(
        ar(f"المتعاقد عليه: {c.visits_per_year or 0} زيارة سنويًا  |  "
           f"المنفّذة: {c.visits_done}  |  المتبقية: {c.visits_remaining}"),
        styles["BodyMuted"]))
    story.append(Spacer(1, 2 * mm))

    if c.visits:
        vheader = [ar(h) for h in ["م", "التاريخ", "الفني", "الحالة", "ملاحظات"]]
        vrows = []
        for i, v in enumerate(c.visits, start=1):
            st = {"Scheduled": "مجدولة", "Done": "منفّذة",
                  "Missed": "فائتة"}.get(v.status, v.status or "—")
            if v.is_overdue:
                st = "متأخرة"
            vrows.append([
                str(i),
                str(v.visit_date) if v.visit_date else "—",
                ar(v.technician or "—"),
                ar(st),
                ar(v.notes or v.findings or "—"),
            ])
        vt = _data_table(vheader, vrows,
                         [10 * mm, 26 * mm, 34 * mm, 24 * mm, 76 * mm])
        extra = []
        for i, v in enumerate(c.visits, start=1):
            if v.status == "Done":
                bg = colors.HexColor("#d4edda")
            elif v.is_overdue or v.status == "Missed":
                bg = colors.HexColor("#f8d7da")
            else:
                bg = None
            if bg is not None:
                extra.append(("BACKGROUND", (3, i), (3, i), bg))
        if extra:
            vt.setStyle(TableStyle(extra))
        story.append(vt)
    else:
        story.append(Paragraph(ar("لا توجد زيارات مسجّلة لهذا العقد."),
                               styles["BodyMuted"]))

    if c.notes:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(ar("ملاحظات"), styles["SectionHeader"]))
        story.append(Paragraph(ar(c.notes), styles["Normal"]))

    _report_foot(story, styles, cfg)
    doc.build(story)
    return path


def generate_inspections_report_pdf(equipment_list, path, settings=None,
                                    title="تقرير الفحوصات الدورية للمعدات"):
    """
    equipment_list: قائمة كائنات Equipment (مرتّبة كما نريد عرضها).
    يعرض حالة كل معدة وموعد فحصها القادم مع تلوين الصفوف المتأخرة.
    """
    cfg = dict(settings) if settings else _load_company_settings()
    styles = _styles()
    doc = _doc(path, landscape_mode=True)
    story = []

    # إحصاء سريع حسب الحالة
    counts = {"overdue": 0, "unknown": 0, "soon": 0, "none": 0}
    for e in equipment_list:
        counts[e.alert_level] = counts.get(e.alert_level, 0) + 1

    _report_head(
        story, styles, cfg, title,
        f"إجمالي المعدات: {len(equipment_list)}  |  "
        f"متأخرة: {counts['overdue']}  |  "
        f"لم تُفحص: {counts['unknown']}  |  "
        f"قريبة: {counts['soon']}  |  "
        f"سليمة: {counts['none']}"
    )

    if not equipment_list:
        story.append(Paragraph(ar("لا توجد معدات مسجّلة."), styles["Normal"]))
        _report_foot(story, styles, cfg)
        doc.build(story)
        return path

    label = {"overdue": "متأخر", "soon": "قريب", "none": "سليم", "unknown": "لم يُفحص"}
    header = [ar(h) for h in [
        "م", "المعدة", "النوع", "المشروع", "الموقع",
        "آخر فحص", "الدورة (يوم)", "الفحص القادم", "المتبقي", "التنبيه"
    ]]

    rows = []
    row_colors = []
    for idx, e in enumerate(equipment_list, start=1):
        d = e.days_until_due
        if d is None:
            remaining = "—"
        elif d < 0:
            remaining = f"متأخر ({abs(d)} يوم)"
        else:
            remaining = f"باقٍ ({d} يوم)"
        nxt = e.next_inspection_date
        rows.append([
            str(idx),
            ar(e.name or "-"),
            ar(e.equipment_type or "-"),
            ar(e.project.name if e.project else "-"),
            ar(e.location or "-"),
            str(e.last_inspection_date) if e.last_inspection_date else "—",
            str(e.interval_days or "-"),
            str(nxt) if nxt else "—",
            ar(remaining),
            ar(label.get(e.alert_level, "-")),
        ])
        row_colors.append(e.alert_level)

    widths = [10 * mm, 45 * mm, 30 * mm, 50 * mm, 32 * mm,
              23 * mm, 18 * mm, 23 * mm, 24 * mm, 20 * mm]
    t = _data_table(header, rows, widths)

    # تلوين خانة التنبيه حسب الخطورة — يسهّل القراءة السريعة
    tint = {
        "overdue": colors.HexColor("#f8d7da"),
        "unknown": colors.HexColor("#e2e3e5"),
        "soon": colors.HexColor("#fff3cd"),
        "none": colors.HexColor("#d4edda"),
    }
    extra = []
    for i, lvl in enumerate(row_colors, start=1):
        if lvl in tint:
            extra.append(("BACKGROUND", (9, i), (9, i), tint[lvl]))
    t.setStyle(TableStyle(extra))
    story.append(t)

    _report_foot(story, styles, cfg)
    doc.build(story)
    return path


# ---------------------------------------------------------------------------
# التقرير الشامل لكل المشاريع
# ---------------------------------------------------------------------------

def generate_projects_summary_pdf(projects, path, settings=None,
                                  title="التقرير الشامل للمشاريع"):
    """
    projects: قائمة كائنات Project.
    يعرض جدول المشاريع مع ملخّص مالي وتوزيع الحالات.
    """
    cfg = dict(settings) if settings else _load_company_settings()
    cur = cfg.get("currency") or ""
    styles = _styles()
    doc = _doc(path, landscape_mode=True)
    story = []

    total_invoiced = sum(p.total_invoiced for p in projects)
    total_unpaid = sum(p.total_unpaid for p in projects)

    _report_head(
        story, styles, cfg, title,
        f"عدد المشاريع: {len(projects)}  |  "
        f"إجمالي الفواتير: {total_invoiced:,.2f} {cur}  |  "
        f"غير المسدد: {total_unpaid:,.2f} {cur}"
    )

    if not projects:
        story.append(Paragraph(ar("لا توجد مشاريع مسجّلة."), styles["Normal"]))
        _report_foot(story, styles, cfg)
        doc.build(story)
        return path

    # توزيع الحالات
    status_counts = {}
    for p in projects:
        key = p.status or "غير محدد"
        status_counts[key] = status_counts.get(key, 0) + 1
    dist = "  |  ".join(f"{k}: {v}" for k, v in status_counts.items())
    story.append(Paragraph(ar("توزيع المشاريع حسب الحالة"), styles["SectionHeader"]))
    story.append(Paragraph(ar(dist), styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph(ar("تفاصيل المشاريع"), styles["SectionHeader"]))
    header = [ar(h) for h in [
        "#", "المشروع", "العميل", "الموقع", "النطاق",
        "الحالة", "البدء", "الانتهاء", "المعدات", "الفواتير", "غير المسدد"
    ]]

    rows = []
    for p in projects:
        rows.append([
            str(p.id),
            ar(p.name or "-"),
            ar(p.client_name or "-"),
            ar(p.site or "-"),
            ar(p.scope or "-"),
            ar(p.status or "-"),
            str(p.start_date) if p.start_date else "—",
            str(p.end_date) if p.end_date else "—",
            str(len(p.equipment)),
            f"{p.total_invoiced:,.2f}",
            f"{p.total_unpaid:,.2f}",
        ])

    # صف الإجمالي
    rows.append([
        "", _cell(ar("الإجمالي"), bold=True), "", "", "", "", "", "",
        _cell(str(sum(len(p.equipment) for p in projects)), bold=True),
        _cell(f"{total_invoiced:,.2f}", bold=True, align=TA_RIGHT),
        _cell(f"{total_unpaid:,.2f}", bold=True, align=TA_RIGHT),
    ])

    widths = [10 * mm, 48 * mm, 40 * mm, 26 * mm, 32 * mm,
              20 * mm, 22 * mm, 22 * mm, 16 * mm, 24 * mm, 24 * mm]
    t = _data_table(header, rows, widths, align_right_cols=(9, 10))
    last = len(rows)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, last), (-1, last), colors.HexColor("#e9ecef")),
        ("FONTNAME", (0, last), (-1, last), _ARABIC_BOLD_NAME),
    ]))
    story.append(t)

    _report_foot(story, styles, cfg)
    doc.build(story)
    return path


def generate_project_report_pdf(project, path, company_name=None, settings=None):
    """
    project: كائن Project (مع علاقات client / invoices / equipment محمّلة)
    path: مسار ملف الـ PDF الناتج
    settings: قاموس إعدادات المنشأة. إن لم يُمرَّر تُقرأ من ملف الإعدادات.
    company_name: للتوافق مع الاستدعاءات القديمة؛ يتجاوز الاسم في الإعدادات.
    """
    cfg = dict(settings) if settings else _load_company_settings()
    if company_name:
        cfg["company_name"] = company_name

    styles = _styles()
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm
    )
    story = []

    story.extend(_build_letterhead(cfg, styles))
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
        _cur = cfg.get("currency") or ""
        story.append(Paragraph(
            ar(f"إجمالي الفواتير: {total:,.2f} {_cur} — غير المسدد: {unpaid:,.2f} {_cur}"),
            styles["BodyMuted"]
        ))

    # كان هنا تكرار لمنطق التذييل، فلم يرث تحسيناته (منها رقم الإصدار).
    story.append(Spacer(1, 4))
    _report_foot(story, styles, cfg)

    doc.build(story)
    return path
