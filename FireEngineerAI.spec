# -*- mode: python ; coding: utf-8 -*-
"""
إعداد تغليف FireEngineerAI إلى ملف exe واحد.

    pyinstaller FireEngineerAI.spec --clean --noconfirm

الناتج: dist\\FireEngineerAI.exe

ملاحظات مقصودة:
  * onefile: ملف واحد ينسخه المستخدم أينما شاء.
  * console=False: لا تظهر نافذة سوداء خلف الواجهة.
  * الخطوط والأيقونة مضمَّنة عبر datas — وبدونها تظهر العربية في PDF
    محرّفة، لأن reportlab لا يملك خطًا عربيًا مدمجًا.
  * البيانات (قاعدة البيانات، النسخ، التقارير) تُخزَّن في
    %APPDATA%\\FireEngineerAI خارج الـ exe، فلا تُفقد عند التحديث.
"""

import os

block_cipher = None

datas = [
    ("fonts", "fonts"),            # الخط العربي وغامقه — إلزامي لتقارير PDF
    ("app_icon.ico", "."),
    ("app_icon.png", "."),
]

# استبعاد مكتبات ثقيلة لا يستوردها البرنامج — توفّر عشرات الميغابايت
excludes = [
    "tkinter", "unittest", "pydoc_data",
    "numpy", "pandas", "matplotlib", "scipy",
    "PIL.ImageQt", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtQuick",
    "PySide6.QtQml", "PySide6.Qt3DRender", "PySide6.QtNetworkAuth",
    "PySide6.QtBluetooth", "PySide6.QtPositioning", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSql",
]

hiddenimports = [
    "reportlab.graphics.barcode.code128",
    "reportlab.pdfbase._fontdata_enc_winansi",
    "reportlab.pdfbase._fontdata_enc_macroman",
    "sqlalchemy.dialects.sqlite",
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="FireEngineerAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                     # UPX يرفع احتمال إنذار مكافح الفيروسات
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                 # تطبيق نافذي بلا نافذة أوامر
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="app_icon.ico",
)
