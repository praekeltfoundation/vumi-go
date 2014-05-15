from setuptools import setup, find_packages


setup(
    name="vumi-go",
    version="0.5.0-dev",
    url='http://github.com/praekelt/vumi-go',
    license='BSD',
    description="Vumi Go",
    long_description=open('README.rst', 'r').read(),
    author='Praekelt Foundation',
    author_email='dev@praekeltfoundation.org',
    packages=find_packages(),
    install_requires=[
        'vumi>0.4',
        'vxpolls',
        'vumi-wikipedia',
        # We need dev versions of the three packages above, so they have to be
        # installed before us. They're listed first so that we fail fast
        # instead of working through all the other requirements before
        # discovering that they aren't available should that be the case.
        'Django==1.5.8',
        'gunicorn==0.15.0',
        'South==0.8.2',
        'psycopg2==2.4',
        'celery==3.0.23',
        'django-celery==3.0.23',
        'django-celery-email',
        'Markdown==2.1.1',
        'django-registration==1.0',
        'lesscpy==0.9h',
        'xlrd==0.8.0',
        'requests==0.14.2',
        'mock==1.0.1',
        'raven>=2.0,<3.0',
        'django-debug-toolbar==0.9.4',
        'kombu==2.5.6',
        'librabbitmq==1.0.1',
        'hiredis==0.1.1',
        'django-pipeline==1.3.6',
        'txpostgres==1.1.0',
        'django-crispy-forms==1.4.0',
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
