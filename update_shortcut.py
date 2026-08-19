"""
تحويل اختصار سطح المكتب إلى ملف exe

    python update_shortcut.py

قبل التشغيل: تأكد أن dist\\FireEngineerAI.exe يعمل وأن تقارير PDF تخرج
بعربية سليمة. الاختصار الحالي يشغّل الكود المصدري عبر pythonw.exe،
وهذا السكربت يحوّله ليشغّل الـ exe مباشرة (بلا حاجة لبايثون).

للتراجع: شغّل create_shortcut.ps1 مرة أخرى.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

PS = r'''
$ErrorActionPreference = "Stop"
$exe  = "{exe}"
$icon = "{icon}"
$work = "{work}"

function Set-AppShortcut($LinkPath) {{
    $shell = New-Object -ComObject WScript.Shell
    $sc = $shell.CreateShortcut($LinkPath)
    $sc.TargetPath       = $exe
    $sc.Arguments        = ""
    $sc.WorkingDirectory = $work
    $sc.IconLocation     = "$icon,0"
    $sc.Description      = "FireEngineerAI - نظام إدارة مشاريع الحماية من الحريق"
    $sc.Save()
    Write-Host "  [تم] $LinkPath"
}}

$desktop = [Environment]::GetFolderPath("Desktop")
Set-AppShortcut (Join-Path $desktop "FireEngineerAI.lnk")

$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "FireEngineerAI"
if (-not (Test-Path $startMenu)) {{ New-Item -ItemType Directory -Path $startMenu | Out-Null }}
Set-AppShortcut (Join-Path $startMenu "FireEngineerAI.lnk")
'''


def main():
    if os.name != "nt":
        print("\n[خطأ] هذا السكربت لنظام Windows فقط.\n")
        return 1

    exe = os.path.join(HERE, "dist", "FireEngineerAI.exe")
    if not os.path.exists(exe):
        print("\n[توقّف] لا يوجد dist\\FireEngineerAI.exe")
        print("        شغّل أولًا:  python build_exe.py\n")
        return 1

    icon = os.path.join(HERE, "app_icon.ico")
    if not os.path.exists(icon):
        icon = exe          # الأيقونة مدمجة في الـ exe نفسه

    print("\n=== تحويل الاختصار إلى ملف exe ===\n")
    print(f"  الهدف: {exe}")
    print(f"  الحجم: {os.path.getsize(exe) / (1024*1024):.0f} ميغابايت\n")

    script = PS.format(exe=exe, icon=icon, work=os.path.join(HERE, "dist"))
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]
    )
    if r.returncode != 0:
        print("\n[خطأ] فشل تحديث الاختصار.\n")
        return 1

    print("\n" + "=" * 52)
    print("  تم. أيقونة سطح المكتب تشغّل الـ exe الآن.")
    print("=" * 52)
    print("\nلم يعد تشغيل البرنامج يحتاج بايثون مثبَّتًا.")
    print("للتراجع: شغّل create_shortcut.ps1 مرة أخرى.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
