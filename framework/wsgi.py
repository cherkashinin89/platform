# wsgi.py - точка входа для Gunicorn
from app import app as application

if __name__ == '__main__':
    application.run()
