@echo off
echo Iniciando aplicação Flask com Gunicorn...
gunicorn app:app --bind 0.0.0.0:5000
pause