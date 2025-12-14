@echo off
chcp 65001 >nul
title Sinf Websayt - Server
color 0B

echo ========================================
echo    SINF WEBSAYT - SERVER
echo ========================================
echo.

cd /d "%~dp0"

echo Kutubxonalar tekshirilmoqda...
python -c "import flask; import flask_socketio; import apscheduler" >nul 2>&1
if errorlevel 1 (
    echo [XATO] Kutubxonalar o'rnatilmagan!
    echo Avval "install.bat" ni ishga tushiring.
    pause
    exit /b 1
)
echo [OK] Barcha kutubxonalar mavjud.
echo.

echo ========================================
echo    SERVER ISHGA TUSHMOQDA...
echo ========================================
echo.
echo    Manzil: http://127.0.0.1:8080
echo.
echo    Yopish uchun: Ctrl+C yoki oynani yoping
echo ========================================
echo.

start "" "http://127.0.0.1:8080"

python app.py

pause
