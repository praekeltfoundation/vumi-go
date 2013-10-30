import os
from settings import *

SECRET_KEY = "test_secret"

# This needs to point at the test riak buckets.
VUMI_API_CONFIG['riak_manager'] = {'bucket_prefix': 'test.'}
VUMI_API_CONFIG['redis_manager'] = {
    'key_prefix': 'test',
    'FAKE_REDIS': 'sure',
}

# Setup test database

VUMIGO_TEST_DB = os.environ.get('VUMIGO_TEST_DB', 'sqlite')

if VUMIGO_TEST_DB == "sqlite":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': 'go.db',
        }
    }

elif VUMIGO_TEST_DB == "postgres":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'go',
            'USER': 'go',
            'PASSWORD': 'go',
            'HOST': 'localhost',
        }
    }

elif VUMIGO_TEST_DB == "memory":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }

else:
    raise ValueError("Invalid value %r for VUMIGO_TEST_DB"
                     % VUMIGO_TEST_DB)

del VUMIGO_TEST_DB

# celery likes to eagerly close and restart database connections
# which combines badly with tests run inside transactions. If this
# threshold is reached (i.e. a test runs more than this many celery
# tasks) celery will close the database connection and create a new
# one and the test will fail in strange ways (e.g. the user the django
# test client was logged in as will suddenly not exist).
CELERY_DB_REUSE_MAX = 100

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

NOSE_ARGS = ['-evumitools', '-evumi_app', '-ehandlers', '-m^test']

MESSAGE_STORAGE = 'django.contrib.messages.storage.cookie.CookieStorage'
STATICFILES_STORAGE = 'pipeline.storage.NonPackagingPipelineStorage'

# disable console logging to avoid log messages messing up test output
LOGGING['loggers']['go']['handlers'].remove('console')
