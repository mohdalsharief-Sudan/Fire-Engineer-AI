"""
settings.py
إعدادات المنشأة (اسم الشركة، الشعار، معلومات التواصل) التي تظهر في ترويسة
تقارير الـ PDF.

تُحفظ في ملف JSON بجانب قاعدة البيانات داخل مجلد بيانات البرنامج، وليس داخل
مجلد الكود — حتى لا تضيع عند تحديث البرنامج أو سحب نسخة جديدة من GitHub.
"""

import json
import os
import shutil

from database import BASE_DIR

SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")
LOGO_PATH = os.path.join(BASE_DIR, "company_logo.png")

DEFAULTS = {
    "company_name": "",
    "company_name_en": "",
    "cr_number": "",          # السجل التجاري
    "vat_number": "",         # الرقم الضريبي
    "phone": "",
    "email": "",
    "website": "",
    "address": "",
    "report_footer": "تم إنشاء هذا التقرير آليًا بواسطة FireEngineerAI",
    "logo_path": "",
    "currency": "ريال",
}


def load_settings():
    """يقرأ الإعدادات المحفوظة، ويكمل أي مفتاح ناقص بالقيمة الافتراضية."""
    data = dict(DEFAULTS)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                # نأخذ المفاتيح المعروفة فقط لتفادي مفاتيح تالفة
                for k in DEFAULTS:
                    if k in saved and saved[k] is not None:
                        data[k] = saved[k]
        except Exception as e:
            print("تحذير: تعذر قراءة ملف الإعدادات، سيتم استخدام الافتراضي:", e)
    return data


def save_settings(data):
    """
    يحفظ الإعدادات. يكتب في ملف مؤقت ثم يستبدل الأصلي، حتى لا يتلف الملف
    إذا انقطعت الكتابة في المنتصف.
    """
    clean = {k: data.get(k, DEFAULTS[k]) for k in DEFAULTS}
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS_PATH)
    return clean


def save_logo(source_path):
    """
    ينسخ الشعار إلى مجلد بيانات البرنامج ويعيد مساره الجديد.

    سبب النسخ: لو خزّنّا مسار الصورة الأصلي فقط، فحذفها المستخدم أو نقلها
    سيؤدي إلى اختفاء الشعار من التقارير لاحقًا.
    """
    if not source_path or not os.path.exists(source_path):
        return ""
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise ValueError("صيغة الصورة غير مدعومة. استخدم PNG أو JPG.")
    dest = os.path.join(BASE_DIR, "company_logo" + ext)
    shutil.copy2(source_path, dest)
    return dest


def clear_logo(current_path):
    """يحذف ملف الشعار المخزّن (إن وُجد)."""
    try:
        if current_path and os.path.exists(current_path) \
                and os.path.dirname(current_path) == BASE_DIR:
            os.remove(current_path)
    except Exception:
        pass
    return ""
