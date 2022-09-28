#!/bin/bash

echo "RUN SERVER"

bash ./wait-for-it.sh -h db -p 5432 -t 120

sleep 5

python manage.py migrate

python manage.py initadmin

python manage.py collectstatic --noinput

python manage.py runserver 0.0.0.0:8000
