@echo off
REM تشغيل اختبارات FireEngineerAI - انقر مرتين على هذا الملف
cd /d "%~dp0"
echo.
echo === اختبارات FireEngineerAI ===
echo.
python -m pytest tests -v
echo.
pause
