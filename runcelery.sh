#!/bin/bash

bash ./wait-for-it.sh -h db -p 5432 -t 120

bash ./wait-for-it.sh -h app -p 8000 -t 20

sleep 5

python manage.py migrate django_celery_results

celery -A codice.celery worker --loglevel=info
