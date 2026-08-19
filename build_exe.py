"""
بناء ملف FireEngineerAI.exe

    python build_exe.py

يفحص المتطلبات أولًا، يشغّل الاختبارات، ثم يبني. البناء يستغرق 2-5 دقائق.
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REQUIRED = ["app.py", "database.py", "reports.py", "applog.py",
            "theme.py", "settings.py", "app_icon.ico",
            "FireEngineerAI.spec"]


def fail(msg):
    print(f"\n[توقّف] {msg}\n")
    return 1


def main():
    os.chdir(HERE)
    print("\n=== بناء FireEngineerAI.exe ===\n")

    # 1) الملفات الأساسية
    missing = [f for f in REQUIRED if not os.path.exists(os.path.join(HERE, f))]
    if missing:
        return fail("ملفات ناقصة: " + "، ".join(missing))
    print("  [1/5] الملفات الأساسية موجودة")

    # 2) الخطوط — بدونها تخرج العربية محرّفة في PDF
    font = os.path.join(HERE, "fonts", "Arabic.ttf")
    if not os.path.exists(font):
        return fail("لا يوجد fonts\\Arabic.ttf — ستخرج تقارير PDF بعربية محرّفة.")
    print("  [2/5] الخط العربي موجود")

    # 3) PyInstaller
    try:
        import PyInstaller  # noqa: F401
        print("  [3/5] PyInstaller مثبَّت")
    except ImportError:
        print("  [3/5] PyInstaller غير مثبَّت — جارٍ التثبيت...")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])
        if r.returncode != 0:
            return fail("فشل تثبيت PyInstaller.")

    # 4) الاختبارات — لا نغلّف كودًا مكسورًا
    if os.path.isdir(os.path.join(HERE, "tests")):
        print("  [4/5] تشغيل الاختبارات...")
        r = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"])
        if r.returncode != 0:
            return fail("الاختبارات سقطت. أصلحها قبل التغليف.")
    else:
        print("  [4/5] لا يوجد مجلد tests — تخطٍّ")

    # 5) البناء
    print("  [5/5] البناء... (2-5 دقائق، لا تغلق النافذة)\n")
    for d in ("build", "dist"):
        shutil.rmtree(os.path.join(HERE, d), ignore_errors=True)

    r = subprocess.run([sys.executable, "-m", "PyInstaller",
                        "FireEngineerAI.spec", "--clean", "--noconfirm"])
    if r.returncode != 0:
        return fail("فشل البناء. راجع الرسائل أعلاه.")

    exe = os.path.join(HERE, "dist", "FireEngineerAI.exe")
    if not os.path.exists(exe):
        return fail("انتهى البناء لكن الملف غير موجود.")

    mb = os.path.getsize(exe) / (1024 * 1024)
    print("\n" + "=" * 55)
    print(f"  تم:  dist\\FireEngineerAI.exe   ({mb:.0f} ميغابايت)")
    print("=" * 55)
    print("\nالخطوة التالية: انقر عليه مرتين وجرّب إصدار تقرير PDF")
    print("للتأكد من ظهور العربية سليمة.\n")
    print("تنبيه: قد يعترض Windows SmartScreen في أول تشغيل —")
    print("       اضغط \"More info\" ثم \"Run anyway\". السبب أن الملف")
    print("       غير موقَّع رقميًا، وهذا طبيعي للبرامج الداخلية.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
