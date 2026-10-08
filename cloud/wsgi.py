# wsgi.py - Точка входа для Gunicorn
#
# Gunicorn будет импортировать `application` из этого модуля.
# Запуск: gunicorn -b 127.0.0.1:5002 wsgi:application
from app import app as application


if __name__ == '__main__':
    application.run()
