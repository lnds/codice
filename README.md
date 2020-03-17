# codice

Códice it's a code quality evaluation tool.

Códice es una herramienta para evaluar calidad del código.

## Requirements

This release requires 

- Python 3.8.
- Pipenv
- Posgresql 9.7+    
- RabbitMq

## Instructions for stand alone development

Create an empty postgresql database (see codice/settings.py for default username and passwords in develop mode).

Is recommended to define the environment variable DATABASE_URL with the postgresql login credentials

Execute these steps:

    $ git clone <codice>
    
    $ cd codice
    
    $ pipenv install --python `which python3.X` # replace X by 6 or 7
    
    $ pipenv shell
        
    $ pipenv sync --dev # install all neded packages
    
    $ python manage.py makemigrations
    
    $ python manage.py migrate
    
    $ python manage.py createsuperuser
    
    $ # complete admin creation
    
    $ rabbitmq-server &
    
Start two shells, one for codice-server and another for celery:

    $ celery -A codice.celery_app:app worker --loglevel=info
    
    $ python manage.py runserver


Visit: http://localhost:8080/

Now you are ready to start using Códice.

## GUI

Theme taken from: https://github.com/flatlogic/light-blue-dashboard


# Copyright 

See LICENSE file

(c) 2020 Eduardo Díaz Cortés
