#!/usr/bin/env python
"""
Стабильный запуск Django сервера без автоматической перезагрузки
"""
import os
import sys
import django
from django.core.management import execute_from_command_line

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legalai.settings')
    
    # Запуск сервера без автоматической перезагрузки
    sys.argv = ['manage.py', 'runserver', '--noreload', '127.0.0.1:8000']
    
    try:
        execute_from_command_line(sys.argv)
    except KeyboardInterrupt:
        print("\nСервер остановлен пользователем")
        sys.exit(0)
