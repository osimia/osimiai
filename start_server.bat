@echo off
echo Запуск стабильного Django сервера...
echo.

REM Активация виртуального окружения
call .venv\Scripts\activate.bat

REM Запуск сервера без автоматической перезагрузки
python manage.py runserver --noreload 127.0.0.1:8000

pause
