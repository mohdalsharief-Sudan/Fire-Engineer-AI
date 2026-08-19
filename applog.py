"""
applog.py
نظام تسجيل الأحداث والأخطاء + النسخ الاحتياطي الآمن لبرنامج FireEngineerAI.

سبب وجود هذا الملف:
لم يكن في البرنامج أي تسجيل للأخطاء، فإذا وقع خطأ عند المستخدم لا يبقى منه
أثر بعد إغلاق البرنامج — وكان كل تشخيص يبدأ من الصفر بلقطة شاشة وتخمين.
كما كان أي خطأ غير متوقع يُغلق البرنامج فجأة بلا رسالة، وربما وسط إدخال بيانات.
"""

import os
import sys
import glob
import shutil
import sqlite3
import logging
import traceback
from datetime import datetime, date
from logging.handlers import RotatingFileHandler

# رقم إصدار البرنامج — يظهر في شريط العنوان وتذييل التقارير.
# ارفعه مع كل تحديث ملموس حتى يمكن معرفة أي نسخة تعمل عند المستخدم.
__version__ = "1.5.2"
APP_VERSION = __version__

_LOGGER_NAME = "fireengineer"
_configured = False


# ---------------------------------------------------------------------------
# التسجيل (Logging)
# ---------------------------------------------------------------------------

def setup_logging(base_dir, level=logging.INFO):
    """
    يهيّئ ملف السجل داخل <base_dir>/logs/app.log.

    يُستخدم RotatingFileHandler حتى لا ينمو الملف بلا حد: عند بلوغه 1 ميجابايت
    يُؤرشف ويُبدأ ملف جديد، مع الاحتفاظ بآخر 5 ملفات.

    آمن تمامًا: إن تعذّرت الكتابة (صلاحيات، قرص ممتلئ) لا يتعطل البرنامج،
    بل يكتفي بالتسجيل في الذاكرة/الكونسول.
    """
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        log_dir = os.path.join(base_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        fh = RotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            maxBytes=1_000_000, backupCount=5, encoding="utf-8",
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass  # لا نُسقط البرنامج بسبب فشل التسجيل

    # نافذة الكونسول غير ظاهرة مع pythonw، لكنها مفيدة عند التشغيل للتطوير
    try:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)
    except Exception:
        pass

    _configured = True
    logger.info("=" * 60)
    logger.info("بدء تشغيل FireEngineerAI الإصدار %s", __version__)
    logger.info("بايثون %s | المنصة %s", sys.version.split()[0], sys.platform)
    return logger


def get_logger(name=None):
    """يعيد مسجّلًا فرعيًا. يعمل حتى قبل setup_logging."""
    if name:
        return logging.getLogger(f"{_LOGGER_NAME}.{name}")
    return logging.getLogger(_LOGGER_NAME)


def log_path(base_dir):
    return os.path.join(base_dir, "logs", "app.log")


# ---------------------------------------------------------------------------
# معالج الأخطاء غير المتوقعة
# ---------------------------------------------------------------------------

def install_excepthook(base_dir, parent=None):
    """
    يلتقط أي خطأ غير معالَج بدل أن يختفي البرنامج فجأة.

    يسجّل الخطأ كاملًا في ملف السجل، ثم يعرض رسالة عربية مفهومة مع إتاحة
    فتح ملف السجل. البرنامج يبقى يعمل ما أمكن، فقد يكون الخطأ في عملية
    واحدة لا في البرنامج كله — وإغلاقه يعني ضياع ما لم يُحفظ.
    """
    logger = get_logger("crash")

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical("خطأ غير متوقع:\n%s", details)

        try:
            from PySide6.QtWidgets import QMessageBox, QApplication
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl

            if QApplication.instance() is None:
                return

            box = QMessageBox(parent)
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle("خطأ غير متوقع")
            box.setText(
                "حدث خطأ غير متوقع.\n\n"
                "لم يُغلق البرنامج، لكن يُنصح بحفظ عملك وإعادة التشغيل.\n"
                "حُفظت تفاصيل الخطأ في ملف السجل."
            )
            box.setInformativeText(f"{exc_type.__name__}: {exc_value}")
            box.setDetailedText(details)
            open_btn = box.addButton("فتح ملف السجل", QMessageBox.ActionRole)
            box.addButton("إغلاق", QMessageBox.AcceptRole)
            box.exec()

            if box.clickedButton() is open_btn:
                QDesktopServices.openUrl(QUrl.fromLocalFile(log_path(base_dir)))
        except Exception:
            # لا نسمح لخطأ داخل معالج الأخطاء بإسقاط البرنامج
            pass

    sys.excepthook = _hook


# ---------------------------------------------------------------------------
# النسخ الاحتياطي
# ---------------------------------------------------------------------------

def _sqlite_safe_copy(src, dest):
    """
    ينسخ قاعدة SQLite عبر واجهة النسخ الرسمية بدل نسخ الملف.

    shutil.copy2 على قاعدة قيد الاستخدام قد ينتج ملفًا تالفًا (نسخة غير
    متسقة إن كانت هناك كتابة جارية أو بيانات في ملف WAL). واجهة
    sqlite3.Connection.backup تضمن نسخة متماسكة.
    """
    src_conn = sqlite3.connect(src)
    try:
        dest_conn = sqlite3.connect(dest)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()


def verify_backup(path):
    """يتحقق أن ملف النسخة سليم وقابل للفتح (PRAGMA integrity_check)."""
    try:
        conn = sqlite3.connect(path)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            return bool(row) and row[0] == "ok"
        finally:
            conn.close()
    except Exception:
        return False


def prune_backups(backups_dir, keep=30):
    """يحذف أقدم النسخ ويُبقي أحدث `keep` نسخة."""
    logger = get_logger("backup")
    try:
        files = sorted(
            glob.glob(os.path.join(backups_dir, "db_backup_*.sqlite3")),
            key=os.path.getmtime, reverse=True,
        )
        for old in files[keep:]:
            try:
                os.remove(old)
                logger.info("حُذفت نسخة قديمة: %s", os.path.basename(old))
            except Exception as e:
                logger.warning("تعذر حذف النسخة %s: %s", old, e)
    except Exception as e:
        logger.warning("تعذر تنظيف النسخ القديمة: %s", e)


def create_backup(db_path, backups_dir, keep=30, verify=True):
    """
    ينشئ نسخة احتياطية موسومة بالتاريخ **والوقت**.

    الخلل الذي يعالجه: كان الاسم يحمل التاريخ فقط (db_backup_2026-08-18)،
    فأي نسخة ثانية في اليوم نفسه تمحو الأولى. والأخطر: لو تلفت البيانات
    ظهرًا ثم أُنشئت نسخة، تُدمَّر النسخة الصباحية السليمة.

    يعيد (نجاح, المسار أو رسالة الخطأ).
    """
    logger = get_logger("backup")
    try:
        os.makedirs(backups_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        dest = os.path.join(backups_dir, f"db_backup_{stamp}.sqlite3")

        # حتى الطابع بالثانية يتصادم إن وقعت نسختان في الثانية نفسها
        # (مثل نسخة الإقلاع التلقائية ثم ضغطة يدوية فورية) — فتمحو
        # إحداهما الأخرى. نضيف لاحقة رقمية لضمان عدم الاستبدال أبدًا.
        if os.path.exists(dest):
            for i in range(2, 100):
                alt = os.path.join(backups_dir, f"db_backup_{stamp}_{i}.sqlite3")
                if not os.path.exists(alt):
                    dest = alt
                    break

        if not os.path.exists(db_path):
            msg = "ملف قاعدة البيانات غير موجود."
            logger.error("%s (%s)", msg, db_path)
            return False, msg

        try:
            _sqlite_safe_copy(db_path, dest)
        except Exception as e:
            # احتياط: إن فشلت واجهة SQLite لأي سبب نعود للنسخ العادي
            logger.warning("فشل النسخ الآمن (%s) — سيُستخدم النسخ العادي", e)
            shutil.copy2(db_path, dest)

        if verify and not verify_backup(dest):
            logger.error("النسخة الناتجة تالفة: %s", dest)
            try:
                os.remove(dest)
            except Exception:
                pass
            return False, "تعذر التحقق من سلامة النسخة الاحتياطية."

        size_kb = os.path.getsize(dest) / 1024
        logger.info("نسخة احتياطية ناجحة: %s (%.1f كيلوبايت)",
                    os.path.basename(dest), size_kb)
        prune_backups(backups_dir, keep=keep)
        return True, dest
    except Exception as e:
        logger.exception("فشل إنشاء النسخة الاحتياطية")
        return False, str(e)


def auto_backup_on_start(db_path, backups_dir, keep=30):
    """
    نسخة احتياطية تلقائية صامتة عند الإقلاع، مرة واحدة يوميًا كحد أقصى.

    سبب وجودها: النسخ اليدوي يعتمد على تذكّر المستخدم، وهذا يفشل دائمًا —
    لا لإهمال بل لأن الانشغال يُنسي. النسخة التلقائية تضمن وجود نقطة
    استرجاع حديثة دائمًا دون أي تدخل.

    يعيد مسار النسخة إن أُنشئت، أو None إن وُجدت نسخة اليوم أو تعذّر ذلك.
    """
    logger = get_logger("backup")
    try:
        if not os.path.exists(db_path):
            return None
        os.makedirs(backups_dir, exist_ok=True)

        today = date.today().isoformat()
        existing = glob.glob(os.path.join(backups_dir, f"db_backup_{today}_*.sqlite3"))
        if existing:
            logger.info("توجد نسخة تلقائية لليوم — تم التخطي")
            return None

        ok, result = create_backup(db_path, backups_dir, keep=keep)
        if ok:
            logger.info("نسخة احتياطية تلقائية عند الإقلاع")
            return result
        logger.warning("تعذرت النسخة التلقائية: %s", result)
        return None
    except Exception:
        logger.exception("خطأ في النسخ الاحتياطي التلقائي")
        return None
