# إنشاء_اختصار.ps1
# ينشئ أيقونة FireEngineerAI على سطح المكتب وفي قائمة ابدأ.
#
# النتيجة: أيقونة باسم "FireEngineerAI" فقط — بلا امتداد ظاهر،
# وبلا نافذة سوداء عند التشغيل (نستخدم pythonw.exe).
#
# التشغيل: كليك يمين على هذا الملف -> Run with PowerShell
# أو من الطرفية:  powershell -ExecutionPolicy Bypass -File .\إنشاء_اختصار.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   إنشاء اختصار FireEngineerAI" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# مجلد المشروع = مجلد هذا السكربت
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$AppScript  = Join-Path $ProjectDir "app.py"
$IconPath   = Join-Path $ProjectDir "app_icon.ico"

if (-not (Test-Path $AppScript)) {
    Write-Host "  [خطأ] لم يُعثر على app.py في:" -ForegroundColor Red
    Write-Host "        $ProjectDir" -ForegroundColor Red
    Write-Host "        ضع هذا السكربت داخل مجلد البرنامج." -ForegroundColor Yellow
    Read-Host "`nاضغط Enter للإغلاق"
    exit 1
}

Write-Host "  مجلد البرنامج : $ProjectDir"

# ---------------------------------------------------------------
# البحث عن pythonw.exe (يشغّل بلا نافذة كونسول سوداء)
# ---------------------------------------------------------------
$PythonW = $null

# 1) بجوار python.exe الموجود في PATH
$pyCmd = Get-Command python.exe -ErrorAction SilentlyContinue
if ($pyCmd) {
    $candidate = Join-Path (Split-Path $pyCmd.Source) "pythonw.exe"
    if (Test-Path $candidate) { $PythonW = $candidate }
}

# 2) عبر py launcher
if (-not $PythonW) {
    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $exe = & py.exe -c "import sys; print(sys.executable)" 2>$null
            if ($exe) {
                $candidate = Join-Path (Split-Path $exe) "pythonw.exe"
                if (Test-Path $candidate) { $PythonW = $candidate }
            }
        } catch { }
    }
}

# 3) المسارات المعتادة للتثبيت
if (-not $PythonW) {
    $guesses = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python" -Directory -ErrorAction SilentlyContinue |
               ForEach-Object { Join-Path $_.FullName "pythonw.exe" }
    foreach ($g in $guesses) {
        if (Test-Path $g) { $PythonW = $g; break }
    }
}

if (-not $PythonW) {
    Write-Host "  [خطأ] لم يُعثر على pythonw.exe" -ForegroundColor Red
    Write-Host "        تأكد أن بايثون مثبّت ومضاف إلى PATH." -ForegroundColor Yellow
    Read-Host "`nاضغط Enter للإغلاق"
    exit 1
}

Write-Host "  مشغّل بايثون  : $PythonW"

if (Test-Path $IconPath) {
    Write-Host "  الأيقونة      : app_icon.ico"
} else {
    Write-Host "  [تنبيه] app_icon.ico غير موجود — سيُستخدم شكل افتراضي." -ForegroundColor Yellow
    $IconPath = $PythonW
}

# ---------------------------------------------------------------
# إنشاء الاختصارات
# ---------------------------------------------------------------
function New-AppShortcut {
    param([string]$Path)

    $shell = New-Object -ComObject WScript.Shell
    $sc = $shell.CreateShortcut($Path)
    $sc.TargetPath       = $PythonW
    $sc.Arguments        = '"' + $AppScript + '"'
    $sc.WorkingDirectory = $ProjectDir
    $sc.IconLocation     = "$IconPath,0"
    $sc.Description      = "نظام إدارة مشاريع الحماية من الحريق"
    $sc.WindowStyle      = 1
    $sc.Save()
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$DesktopLink = Join-Path $Desktop "FireEngineerAI.lnk"
New-AppShortcut -Path $DesktopLink
Write-Host ""
Write-Host "  [تم] أيقونة على سطح المكتب" -ForegroundColor Green

$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$StartLink = Join-Path $StartMenu "FireEngineerAI.lnk"
try {
    New-AppShortcut -Path $StartLink
    Write-Host "  [تم] إدراج في قائمة ابدأ" -ForegroundColor Green
} catch {
    Write-Host "  [تنبيه] تعذر الإضافة لقائمة ابدأ (غير مهم)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  اكتمل. ستجد أيقونة (FireEngineerAI) على سطح المكتب." -ForegroundColor Green
Write-Host ""
Write-Host "  ملاحظة: الاختصار يشير إلى ملفات المشروع في:" 
Write-Host "  $ProjectDir"
Write-Host "  لا تنقل المجلد بعد الآن، وإن نقلته أعد تشغيل هذا السكربت."
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

Read-Host "اضغط Enter للإغلاق"
