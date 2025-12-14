@echo off
chcp 65001 >nul
title Sinf Websayt - Kutubxonalarni O'rnatish
color 0A

echo ========================================
echo    SINF WEBSAYT - O'RNATISH
echo ========================================
echo.

echo [1/4] Python tekshirilmoqda...
python --version >nul 2>&1
if errorlevel 1 (
    echo [XATO] Python topilmadi!
    echo Python o'rnatilganligini tekshiring.
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python topildi.
echo.

echo [2/4] pip yangilanmoqda...
python -m pip install --upgrade pip >nul 2>&1
echo [OK] pip yangilandi.
echo.

echo [3/4] Kutubxonalar o'rnatilmoqda...
echo.
echo     - Flask o'rnatilmoqda...
python -m pip install flask
echo.
echo     - Flask-SocketIO o'rnatilmoqda...
python -m pip install flask-socketio
echo.
echo     - APScheduler o'rnatilmoqda...
python -m pip install apscheduler
echo.

echo [4/4] O'rnatish tekshirilmoqda...
python -c "import flask; import flask_socketio; import apscheduler; print('Barcha kutubxonalar muvaffaqiyatli o''rnatildi!')"
if errorlevel 1 (
    echo [XATO] Ba'zi kutubxonalar o'rnatilmadi!
    pause
    exit /b 1
)

echo.
echo ========================================
echo    O'RNATISH MUVAFFAQIYATLI YAKUNLANDI!
echo ========================================
echo.
echo Endi "run.bat" faylini ishga tushiring.
echo.
pause
