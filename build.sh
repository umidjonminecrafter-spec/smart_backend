#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input

python manage.py migrate academics --fake
python manage.py migrate accounts --fake
python manage.py migrate analytics --fake
python manage.py migrate audit --fake
python manage.py migrate billing --fake
python manage.py migrate communication --fake
python manage.py migrate crm --fake
python manage.py migrate organizations --fake
python manage.py migrate finance --fake
python manage.py migrate tasks --fake
python manage.py migrate