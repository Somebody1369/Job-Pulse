#!/bin/sh
# Starts the web service on Render, which passes quotes in dockerCommand literally.
set -eu
python manage.py migrate --noinput
exec gunicorn config.wsgi:application
