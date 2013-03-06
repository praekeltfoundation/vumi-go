import os
import sys
import types

# protect against importing production settings
for name in ('production_settings', 'go.production_settings'):
    sys.modules[name] = types.ModuleType(name)


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
