from setuptools import setup, find_packages


base_requires = [
    'vumi>=0.5.21',
    'vxsandbox>=0.5.0',
    'vxpolls',
    'vumi-wikipedia>=0.2.1',
    'mock==1.0.1',
    'raven>=2.0,<3.0',
]

django_requires = [
    'Django==1.5.8',
    'gunicorn==0.15.0',
    'South==0.8.2',
    'psycopg2cffi',
    'djorm-ext-core',
    'celery==3.0.23',
    'django-celery==3.0.23',
    # https://github.com/pmclanahan/django-celery-email/pull/14
    'django-celery-email==1.0.4',
    'Markdown==2.1.1',
    'django-registration==1.0',
    'lesscpy==0.9h',
    'xlrd==0.8.0',
    'requests>=1.0',
    'django-debug-toolbar==0.9.4',
    'kombu>=2.5.14,<3.0',
    'librabbitmq==1.5.1',
    'django-pipeline==1.3.6',
    'django-crispy-forms==1.4.0',
    'django-loginas==0.1.3',
    'boto',
    'moto',
    # https://github.com/sehmaschine/django-grappelli/issues/407
    'django-grappelli==2.4.8',
    # The billing API currently pulls in some Django stuff, so its non-Django
    # requirements can live here too.
    'txpostgres>=1.2.0',
]


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
    include_package_data=True,
    install_requires=base_requires,
    extras_require={
        'django': django_requires,
    },
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
