"""
Django settings for codice project.

Generated by 'django-admin startproject' using Django 3.0.3.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/
"""

import os
import re

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '=yz#$q*)s#1inmyltw*kv&4p#7v3nfc21($)r2c9^g4uq#sqk('

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'bootstrap4',
    'fontawesome_5',
    'django_gravatar',
    'mathfilters',
]

LOCAL_APPS = [
    'authentication',
    'dashboard',
    'repos',
    'commits',
    'developers',
    'files',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'codice.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join('codice/templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'codice.context_processors.codice_version',
            ],
        },
    },
]

WSGI_APPLICATION = 'codice.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

if os.environ.get('DATABASE_URL'):
    USER, PASSWORD, HOST, PORT, NAME = re.match(
        "^postgres://(?P<username>.*?)\:(?P<password>.*?)\@(?P<host>.*?)\:(?P<port>\d+)\/(?P<db>.*?)$",
        os.environ.get("DATABASE_URL", "")).groups()
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': NAME,
            'USER': USER,
            'PASSWORD': PASSWORD,
            'HOST': HOST,
            'PORT': int(PORT),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'codice_db',
            'USER': 'codice_user',
            'PASSWORD': 'codice_pass',
        }
    }


BROKER_TRANSPORT_OPTIONS = {'confirm_publish': True}

if 'DOKKU_RABBITMQ_YELLOW_URL' in os.environ:
    CELERY_BROKER_URL = os.environ.get('DOKKU_RABBITMQ_YELLOW_URL', "")
    CELERY_RESULT_BACKEND = os.environ.get('DOKKU_RABBITMQ_YELLOW_URL', "")
elif 'RABBITMQ_URL' in os.environ:
    CELERY_BROKER_URL = os.environ.get('RABBITMQ_URL', "")
    CELERY_RESULT_BACKEND = os.environ.get('RABBITMQ_URL', "")
elif 'RABBIT_ENV_USER' in os.environ:
    CELERY_BROKER_URL = 'pyamqp://{user}:{password}@{hostname}/{vhost}'.format(
        user=os.environ.get('RABBIT_ENV_USER', 'admin'),
        password=os.environ.get('RABBIT_ENV_RABBITMQ_PASS', 'mypass'),
        hostname=os.environ.get('RABBIT_HOSTNAME', 'rabbit'),
        vhost=os.environ.get('RABBIT_VHOST', ''))
else:
    CELERY_BROKER_URL = 'pyamqp://localhost'

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'repos': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
        },
        'dashboard': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
        },
    },
}

# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_URL = '/static/'

STATIC_ROOT = os.environ.get('STATIC', '/static')


STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]


LOGIN_URL = 'login'
LOGOUT_URL = 'logout'
LOGIN_REDIRECT_URL = 'dashboard'

AUTH_USER_MODEL = 'authentication.User'


### Codice Params

CODICE_HOT_SPOTS_THRESHOLD = 30
CODICE_VERSION = "0.1.0"
