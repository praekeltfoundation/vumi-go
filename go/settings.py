
# Django settings for go project.
import os
import djcelery


djcelery.setup_loader()

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))


def abspath(*args):
    """convert relative paths to absolute paths relative to PROJECT_ROOT"""
    return os.path.join(PROJECT_ROOT, *args)


DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('Foundation Developers', 'dev@praekeltfoundation.org'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'go.db',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

INTERNAL_IPS = (
    '127.0.0.1',
    )

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'UTC'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = abspath('media')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = '/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = abspath('static')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
# override this in production_settings.py
SECRET_KEY = ""

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    # 'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'go.base.middleware.VumiUserApiMiddleware',
    'go.base.middleware.ResponseTimeMiddleware',
)

ROOT_URLCONF = 'go.urls'

TEMPLATE_DIRS = (
    abspath("templates"),
    abspath("base", "templates"),
    abspath("conversation", "templates"),
    abspath("contacts", "templates"),
    abspath("account", "templates"),
    abspath("apps", "surveys", "templates"),
    abspath("apps", "multi_surveys", "templates"),
    abspath("apps", "bulk_message", "templates"),
    abspath("apps", "opt_out", "templates"),
    abspath("apps", "sequential_send", "templates"),
    abspath("apps", "wikipedia", "ussd", "templates"),
    abspath("apps", "jsbox", "templates"),
    abspath("apps", "http_api", "templates"),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.flatpages',
    'django.contrib.markup',
    # Uncomment the next line to enable the admin:
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    'django.contrib.admindocs',
    'south',
    'gunicorn',
    'django_nose',
    'djcelery',
    'djcelery_email',
    'go.base',
    'go.conversation',
    'go.contacts',
    'go.account',
    'vxpolls.djdashboard',
    'registration',
    'bootstrap',
    'raven.contrib.django',
    'debug_toolbar',
    'pipeline',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.request",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.static",
    "django.contrib.messages.context_processors.messages",
    "go.base.context_processors.standard_forms",
    "go.base.context_processors.credit",
    "go.base.context_processors.google_analytics",
)

DEBUG_TOOLBAR_CONFIG = {
    'INTERCEPT_REDIRECTS': False,
    'ENABLE_STACKTRACES': True,
}





# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
SKIP_SOUTH_TESTS = True
SOUTH_TESTS_MIGRATE = False
AUTH_PROFILE_MODULE = 'base.UserProfile'

# celery / RabbitMQ configuration

BROKER_HOST = "localhost"
BROKER_PORT = 5672
BROKER_USER = "vumi"
BROKER_PASSWORD = "vumi"
BROKER_VHOST = "/develop"

# If we're running in DEBUG mode then skip RabbitMQ and execute tasks
# immediate instead of deferring them to the queue / workers.
CELERY_ALWAYS_EAGER = DEBUG
CELERY_IMPORTS = ("go.vumitools.api_celery",)
CELERY_RESULT_BACKEND = "amqp"
EMAIL_BACKEND = 'djcelery_email.backends.CeleryEmailBackend'
SEND_FROM_EMAIL_ADDRESS = 'no-reply-vumigo@praekeltfoundation.org'

# Vumi API config
# TODO: go.vumitools.api_worker and this should share the same
#       configuration file so that configuration values aren't
#       duplicated
VUMI_API_CONFIG = {
    'redis_manager': {'key_prefix': 'vumigo', 'db': 1},
    'riak_manager': {'bucket_prefix': 'vumigo.'},
    }

VUMI_INSTALLED_APPS = {
    'go.apps.bulk_message': {
        'namespace': 'bulk_message',
        'display_name': 'Group Message',
    },
    'go.apps.surveys': {
        'namespace': 'survey',
        'display_name': 'Dialogue',
    },
    'go.apps.multi_surveys': {
        'namespace': 'multi_survey',
        'display_name': 'Multiple Dialogues',
    },
    'go.apps.opt_out': {
        'namespace': 'opt_out',
        'display_name': 'Opt Out Handler',
    },
    'go.apps.sequential_send': {
        'namespace': 'sequential_send',
        'display_name': 'Sequential Send',
    },
    'go.apps.subscription': {
        'namespace': 'subscription',
        'display_name': 'Subscription Manager',
    },
    'go.apps.wikipedia.ussd': {
        'namespace': 'wikipedia_ussd',
        'display_name': 'Wikipedia USSD Connection',
    },
    'go.apps.wikipedia.sms': {
        'namespace': 'wikipedia_sms',
        'display_name': 'Wikipedia SMS Connection',
    },
    'go.apps.jsbox': {
        'namespace': 'jsbox',
        'display_name': 'Javascript App',
    },
    'go.apps.http_api': {
        'namespace': 'http_api',
        'display_name': 'HTTP API',
    },
}

VXPOLLS_REDIS_CONFIG = {
    'key_prefix': 'vumigo',
    'db': 1
}
VXPOLLS_PREFIX = 'vxpolls'

# Set this to enable Google Analytics
GOOGLE_ANALYTICS_UA = None

MESSAGE_STORE_API_URL = 'http://localhost:8080/api/v1/'

from celery.schedules import crontab
CELERYBEAT_SCHEDULE = {
    'send-weekly-account-summary': {
        'task': 'go.account.tasks.send_scheduled_account_summary',
        'schedule': crontab(hour=0, minute=0, day_of_week=1),
        'args': ('weekly',)
    },
    'send-daily-account-summary': {
        'task': 'go.account.tasks.send_scheduled_account_summary',
        'schedule': crontab(hour=0, minute=0),
        'args': ('daily',)
    },
}

try:
    from production_settings import *
except ImportError:
    pass

# django-registration tokens expire after a week
ACCOUNT_ACTIVATION_DAYS = 7

# Compress Less with `lesscpy`
COMPRESS_PRECOMPILERS = (
    ('text/less', 'lesscpy {infile} > {outfile}'),
)

if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# Password resets are sent from this address
DEFAULT_FROM_EMAIL = 'Vumi <hello@vumi.org>'

# # Redirect to this URL after a successful login.
# from django.core.urlresolvers import reverse

# LOGIN_REDIRECT_URL = reverse('home')

# PIPELINES CONFIGURATION

STATICFILES_STORAGE = 'pipeline.storage.PipelineCachedStorage'

PIPELINE_CSS = {
    'all': {
        'source_filenames': (
            'bootstrap/css/bootstrap.min.css',
            'css/vumigo.css',
        ),
        'output_filename': 'export/all.css',
    },
}

PIPELINE_JS = {
    'all': {
        'source_filenames': (
            'js/jquery-1.9.1.min.js',
            'bootstrap/js/bootstrap.min.js',
            'js/jquery-ui-1.8.11.custom.min.js',

            'js/go.table.js',
        ),
        'output_filename': 'export/all.js'
    },
}
