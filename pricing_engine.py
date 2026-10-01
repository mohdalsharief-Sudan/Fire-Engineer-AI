"""
pricing_engine.py
─────────────────
محرك حساب التسعير لعروض الحماية من الحرائق.
مبني على منطق fire-pricing/js/api.js و database.js.
يعتمد على library_db (PostgreSQL) للمعدات، ويعيد حسابات التسعير.
مُصمّم ليكون مستقلاً — يُستدعى من تبويب التسعير و/أو تقارير PDF.
"""


from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Any, Optional


def round2(value: float) -> float:
    """تقريب لرقمين عشريين (مطابق لـ Math.round(n * 100) / 100)."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate_selling_price(
    supply_price: float,
    install_price: float,
    profit_percent: float = 25.0,
) -> float:
    """حساب سعر البيع = (سعر الشراء + سعر التثبيت) × (1 + هامش الربح/100)."""
    total_cost = supply_price + install_price
    return round2(total_cost * (1 + profit_percent / 100))


def apply_bulk_price_update(
    items: list[dict],
    pct: float,
    apply_to: str = "both",
) -> list[dict]:
    """
    تحديث أسعار دفعة واحدة (مطابق لـ bulkUpdatePrices في database.js).

    Args:
        items: قائمة specialize بالصفوف (كل صف له supply_price_sar, install_price_sar, id).
        pct: نسبة التغيير المئوية (مثلاً 10 للزيادة 10%، -5 للنقصان 5%).
        apply_to: 'supply' أو 'install' أو 'both'.

    Returns:
        القائمة المنقحة مع تحديث الأسعار وسعر البيع.
    """
    if not pct:
        return items

    factor = 1 + (pct / 100)

    def _round(n: float) -> float:
        return round2(n * factor)

    updated = []
    for item in items:
        ns = item.get("supply_price_sar", 0) or 0
        ni = item.get("install_price_sar", 0) or 0
        if apply_to != "install":
            ns = _round(ns)
        if apply_to != "supply":
            ni = _round(ni)
        selling = calculate_selling_price(ns, ni, item.get("profit_percent", 25))
        updated.append({
            **item,
            "supply_price_sar": ns,
            "install_price_sar": ni,
            "selling_price_sar": selling,
        })
    return updated


def generate_quote_number(existing_quotes: list[dict] | None = None) -> str:
    """
    توليد رقم عرض 새 (مطابق لـ nextQuoteNo في database.js).

    التنسيق: Q-YYYY-NNNN (مثلاً Q-2026-0001).
    """
    year = datetime.now().year
    prefix = f"Q-{year}-"

    max_num = 0
    for q in (existing_quotes or []):
        qn = str(q.get("quote_no") or q.get("quoteNo") or "")
        if not qn.startswith(prefix):
            continue
        try:
            num = int(qn[len(prefix):])
            if num > max_num:
                max_num = num
        except (ValueError, TypeError):
            continue

    return f"{prefix}{str(max_num + 1).zfill(4)}"


def compute_quote_totals(
    items: list[dict],
    margins: dict | None = None,
    vat_percent: float = 15.0,
) -> dict:
    """
    حساب إجماليات العرض الكامل.

    الهيكل (مطابق لـ exportExcel totals في api.js):
        التكلفة الأساسية = مجموع (الكمية × (سعر الشراء + سعر التثبيت))
        النفقات العامة = التكلفة الأساسية × عامل النفقات
        هامش الطوارئ = التكلفة الأساسية × عامل الطوارئ
        هامش الربح = التكلفة الأساسية × عامل الربح
        السعر قبل الضريبة = التكلفة + النفقات + الطوارئ + الربح
        الضريبة (VAT) = السعر قبل الضريبة × نسبة VAT
        الإجمالي النهائي = السعر قبل الضريبة + VAT

    Args:
        items: بنود العرض — كل بند له qty, supply_price_sar, install_price_sar.
        margins: اختياري — dict يحتوي على overheadPct, contingencyPct, profitPct, discountPct.
        vat_percent: نسبة ضريبة القيمة المضافة (الافتراضي 15%).

    Returns:
        dict يحتوي على: base_cost, overhead, contingency, profit, net_before_vat,
        vat, discount, grand_total.
    """
    margins = margins or {}
    overhead_pct = margins.get("overheadPct", margins.get("overhead", 8)) / 100
    contingency_pct = margins.get("contingencyPct", margins.get("contingency", 5)) / 100
    profit_pct = margins.get("profitPct", margins.get("profit", 15)) / 100
    discount_pct = margins.get("discountPct", margins.get("discount", 0)) / 100

    base_cost = 0.0
    for item in items:
        qty = item.get("qty", 0) or 0
        sp = item.get("supply_price_sar", 0) or 0
        ip = item.get("install_price_sar", 0) or 0
        base_cost += qty * (sp + ip)

    base_cost = round2(base_cost)
    overhead = round2(base_cost * overhead_pct)
    contingency = round2(base_cost * contingency_pct)
    profit = round2(base_cost * profit_pct)
    net_before_vat = round2(base_cost + overhead + contingency + profit)
    vat = round2(net_before_vat * vat_percent / 100)
    discount = round2(net_before_vat * discount_pct)
    grand_total = round2(net_before_vat - discount + vat)

    return {
        "base_cost": base_cost,
        "overhead": overhead,
        "contingency": contingency,
        "profit": profit,
        "net_before_vat": net_before_vat,
        "vat": vat,
        "discount": discount,
        "grand_total": grand_total,
    }


def build_quote_summary(
    project: dict,
    items: list[dict],
    margins: dict | None = None,
    vat_percent: float = 15.0,
) -> dict:
    """
    بناء ملخص العرض الكامل (مسودة جاهزة للطباعة أو التصدير).

    يعيد dict يحتوي على جميع حقول المشروع + البنود + الإجماليات.
    """
    totals = compute_quote_totals(items, margins, vat_percent)

    return {
        "quote_no": project.get("quote_no", project.get("quoteNo", "")),
        "client_name": project.get("client_name", project.get("clientName", "")),
        "project_name": project.get("name", ""),
        "location": project.get("location", ""),
        "date": project.get("date", ""),
        "area": project.get("area", 0),
        "floors": project.get("floors", 0),
        "currency": project.get("currency", "SAR"),
        "vat_percent": vat_percent,
        "validity": project.get("validity", 30),
        "status": project.get("status", "draft"),
        "notes": project.get("notes", ""),
        "margins": margins or {},
        "items": items,
        "totals": totals,
    }


# ────────────────────────────────────────
# سجل تاريخ الأسعار (price history)
# ────────────────────────────────────────


class PriceHistory:
    """
    سجل محلي لتغييرات أسعار المعدات (مطابق لـ price_history في database.js).

    يُستخدم لتتبع تغييرات الأسعار عبر الزمن. في الإصدار الحالي
    يعمل في الذاكرة فقط (غير مدمج مع PostgreSQL). يتم التوسع لاحقًا.
    """

    def __init__(self):
        self._records: dict[int, list[dict]] = {}

    def record(
        self,
        item_id: int,
        supply_price: float,
        install_price: float,
        source: str = "يدوي",
    ) -> None:
        """تسجيل تغيير سعر."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "id": len(self._records.get(item_id, [])) + 1,
            "item_id": item_id,
            "supply_cost": round2(supply_price),
            "install_cost": round2(install_price),
            "source": source,
            "changed_at": now,
        }
        self._records.setdefault(item_id, []).append(entry)

    def get_history(self, item_id: int) -> list[dict]:
        """الحصول على سجل تاريخ السعر لجهاز معين (أحدث أولاً)."""
        records = self._records.get(item_id, [])
        return list(reversed(records))

    def clear(self) -> None:
        """مسح السجل (للتجربة/إعادة التهيئة)."""
        self._records.clear()

    def summary(self) -> dict:
        """إحصائية سريعة عن محتوى السجل."""
        total = sum(len(v) for v in self._records.values())
        items = len(self._records)
        return {"total_entries": total, "tracked_items": items}


# ────────────────────────────────────────
# تحويل من تمثل PostgreSQL إلى نموذج التسعير الداخلي
# ────────────────────────────────────────


def library_item_to_pricing_item(eq: Any) -> dict:
    """
    تحويل كائن LibraryEquipment (من SQLAlchemy) إلى dict منسق للتسعير.

    يأخذ كائنًا من library_db.LibraryEquipment ويعيده كـ dict
    له نفس الحقول المستخدمة في.api.js (supply_cost, install_cost, إلخ).
    """
    return {
        "id": getattr(eq, "id", 0),
        "code": getattr(eq, "code", ""),
        "name": getattr(eq, "name", "") or getattr(eq, "model_ar", "") or getattr(eq, "code", ""),
        "brand": getattr(eq, "supplier_name", "") or "",
        "model": getattr(eq, "model", "") or "",
        "unit": "وحدة",
        "supply_cost": getattr(eq, "supply_price_sar", 0) or 0,
        "install_cost": getattr(eq, "install_price_sar", 0) or 0,
        "selling_price": getattr(eq, "selling_price_sar", 0) or 0,
        "profit_percent": getattr(eq, "profit_percent", 25) or 25,
        "category_name": "",
        "currency": getattr(eq, "currency", "SAR") or "SAR",
        "supplier": getattr(eq, "supplier_name", "") or "",
        "is_active": bool(getattr(eq, "is_active", 1)),
        "notes": getattr(eq, "price_note", "") or "",
    }


# ────────────────────────────────────────
# التصدير
# ────────────────────────────────────────

__all__ = [
    "round2",
    "calculate_selling_price",
    "apply_bulk_price_update",
    "generate_quote_number",
    "compute_quote_totals",
    "build_quote_summary",
    "PriceHistory",
    "library_item_to_pricing_item",
]
