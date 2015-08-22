import platform
import sys
from setuptools import setup, find_packages


# We need `psycopg2cffi` for pypy, but `psycopg2` for cpython.
psycopg2 = 'psycopg2==2.4'
# cryptography>=1.0 requires pypy>=2.6.0 because of the new cffi stuff.
cryptography = 'cryptography'
if platform.python_implementation() == "PyPy":
    psycopg2 = 'psycopg2cffi'
    if sys.pypy_version_info < (2, 6):
        cryptography = 'cryptography<1.0'


setup(
    name="vumi-go",
    version="0.5.1a",
    url='http://github.com/praekelt/vumi-go',
    license='BSD',
    description="Vumi Go",
    long_description=open('README.rst', 'r').read(),
    author='Praekelt Foundation',
    author_email='dev@praekeltfoundation.org',
    packages=find_packages(),
    install_requires=[
        cryptography,  # See above for pypy-version-dependent requirement.
        'vumi>=0.5.19',
        'vxsandbox>=0.5.1',
        'vxpolls',
        'vumi-wikipedia>=0.2.0',
        'Django==1.5.8',
        'gunicorn==0.15.0',
        'South==0.8.2',
        psycopg2,  # We choose psycopg2 based on Python implementation above.
        'celery==3.0.23',
        'django-celery==3.0.23',
        # https://github.com/pmclanahan/django-celery-email/pull/14
        'django-celery-email==1.0.4',
        'Markdown==2.1.1',
        'django-registration==1.0',
        'lesscpy==0.9h',
        'xlrd==0.8.0',
        'requests>=1.0',
        'mock==1.0.1',
        'raven>=2.0,<3.0',
        'django-debug-toolbar==0.9.4',
        'kombu>=2.5,<3.0',
        'librabbitmq==1.5.1',
        'hiredis==0.1.4',
        'django-pipeline==1.3.6',
        'txpostgres>=1.2.0',
        'django-crispy-forms==1.4.0',
        'django-loginas==0.1.3',
        'boto',
        'moto',
        # https://github.com/sehmaschine/django-grappelli/issues/407
        'django-grappelli==2.4.8',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Twisted',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Communications',
        'Topic :: Internet',
        'Topic :: System :: Networking',
    ]
)
