import os
from settings import *

# This needs to point at the test riak buckets.
VUMI_API_CONFIG['riak_manager'] = {'bucket_prefix': 'test.'}
VUMI_API_CONFIG['redis_manager'] = {
    'key_prefix': 'test',
    'FAKE_REDIS': 'sure',
    }


if os.environ.get('VUMIGO_FAST_TESTS'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }

NOSE_ARGS = ['-evumitools', '-evumi_app', '-ehandlers', '-m^test']

MESSAGE_STORAGE = 'django.contrib.messages.storage.cookie.CookieStorage'
STATICFILES_STORAGE = 'pipeline.storage.NonPackagingPipelineStorage'
