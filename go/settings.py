
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
    abspath("contacts", "templates"),
    abspath("account", "templates"),
    abspath("apps", "dialogue", "templates"),
    abspath("apps", "surveys", "templates"),
    abspath("apps", "multi_surveys", "templates"),
    abspath("apps", "jsbox", "templates"),
    abspath("conversation", "templates"),
    abspath("router", "templates"),
    abspath("channel", "templates"),
    abspath("routing", "templates"),
    abspath("wizard", "templates"),
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
    'django.contrib.humanize',
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
    'go.router',
    'go.channel',
    'go.wizard',
    'go.contacts',
    'go.account',
    'go.apps.multi_surveys',


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

SESSION_ENGINE = 'go.api.go_api.session'


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

BROKER_HOST = "localhost"
BROKER_PORT = 5672
BROKER_USER = "vumi"
BROKER_PASSWORD = "vumi"
BROKER_VHOST = "/develop"

# If we're running in DEBUG mode then skip RabbitMQ and execute tasks
# immediate instead of deferring them to the queue / workers.
CELERY_ALWAYS_EAGER = DEBUG
CELERY_IMPORTS = (
    "go.contacts.tasks",
    "go.account.tasks",
    "go.conversation.tasks",
)
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
    'go.apps.dialogue': {
        'namespace': 'dialogue',
        'display_name': 'Dialogue',
    },
    'go.apps.surveys': {
        'namespace': 'survey',
        'display_name': 'Old Surveys',
    },
    'go.apps.multi_surveys': {
        'namespace': 'multi_survey',
        'display_name': 'Multiple Old Surveys',
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
    'go.apps.wikipedia': {
        'namespace': 'wikipedia',
        'display_name': 'Wikipedia',
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

VUMI_INSTALLED_ROUTERS = {
    'go.routers.keyword': {
        'namespace': 'keyword',
        'display_name': 'Keyword',
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
GO_API_URL = 'http://localhost:8001/api/v1/go/api'

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


# Compress Less with `lesscpy`
COMPRESS_PRECOMPILERS = (
    ('text/less', 'lesscpy {infile} > {outfile}'),
)

if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# Password resets are sent from this address
DEFAULT_FROM_EMAIL = 'Vumi <hello@vumi.org>'

# AUTH CONFIGURATION
AUTH_PROFILE_MODULE = 'base.UserProfile'
LOGIN_REDIRECT_URL = '/'
# django-registration tokens expire after a week
ACCOUNT_ACTIVATION_DAYS = 7


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

PIPELINE_TEMPLATE_FUNC = '_.template'
PIPELINE_TEMPLATE_NAMESPACE = 'window.JST'
PIPELINE_TEMPLATE_EXT = '.jst'

PIPELINE_JS = {
    'lib': {
        'source_filenames': (
            'js/vendor/base64-2.12.js',
            'js/vendor/uuid-1.4.0.js',
            'js/vendor/jquery-1.9.1.js',
            'js/vendor/lodash.underscore-1.2.1.js',
            'js/vendor/backbone-1.0.0.js',
            'js/vendor/backbone-relational-0.8.5.js',

            'js/vendor/jquery.jsPlumb-1.4.1.js',
            'js/vendor/jquery.ui-1.10.3.js',
            'bootstrap/js/bootstrap.min.js',
            'js/vendor/bootbox.js',
        ),
        'output_filename': 'export/lib.js'
    },
    'go': {
        'source_filenames': (
            'templates/campaign/dialogue/states/modes/preview.jst',
            'templates/campaign/dialogue/states/modes/edit.jst',
            'templates/campaign/dialogue/states/choice/edit.jst',
            'templates/campaign/dialogue/states/choice/preview.jst',
            'templates/campaign/dialogue/states/choice/choice/edit.jst',
            'templates/campaign/dialogue/states/choice/choice/extras.jst',
            'templates/campaign/dialogue/states/freetext/edit.jst',
            'templates/campaign/dialogue/states/freetext/preview.jst',
            'templates/campaign/dialogue/states/end/edit.jst',
            'templates/campaign/dialogue/states/end/preview.jst',
            'templates/campaign/dialogue/states/components/nameExtras.jst',
            'templates/components/confirm.jst',
            'templates/dummy/dummy.jst',

            'js/src/go.js',
            'js/src/utils.js',
            'js/src/errors.js',
            'js/src/components/components.js',
            'js/src/components/rpc.js',
            'js/src/components/models.js',
            'js/src/components/structures.js',
            'js/src/components/views.js',
            'js/src/components/actions.js',
            'js/src/components/grid.js',
            'js/src/components/stateMachine.js',
            'js/src/components/plumbing/plumbing.js',
            'js/src/components/plumbing/endpoints.js',
            'js/src/components/plumbing/states.js',
            'js/src/components/plumbing/connections.js',
            'js/src/components/plumbing/diagrams.js',
            'js/src/components/tables.js',
            'js/src/campaign/campaign.js',
            'js/src/campaign/interactive.js',
            'js/src/campaign/routing/routing.js',
            'js/src/campaign/routing/models.js',
            'js/src/campaign/routing/views.js',
            'js/src/campaign/dialogue/dialogue.js',
            'js/src/campaign/dialogue/models.js',
            'js/src/campaign/dialogue/connections.js',
            'js/src/campaign/dialogue/states/states.js',
            'js/src/campaign/dialogue/states/partials.js',
            'js/src/campaign/dialogue/states/dummy.js',
            'js/src/campaign/dialogue/states/choice.js',
            'js/src/campaign/dialogue/states/freetext.js',
            'js/src/campaign/dialogue/states/end.js',
            'js/src/campaign/dialogue/diagram.js',
            'js/src/campaign/dialogue/style.js',
            'js/src/conversation/conversation.js',
            'js/src/conversation/views.js',
            'js/src/conversation/dashboard.js',
            'js/src/conversation/show.js',

            # TODO This is here so we can access the test model data. This
            # gives us the data we need for a 'demo' of the routing screen.
            # Remove once the screen is hooked up to the API.
            'js/test/tests/campaign/routing/testHelpers.js',
        ),
        'output_filename': 'export/go.js'
    },
}
