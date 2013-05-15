from setuptools import setup, find_packages
import re


def listify(filename):
    return filter(None, open(filename, 'r').read().split('\n'))


_SIMPLE_VERSION_RE = re.compile("(?P<name>.*)-(?P<version>[0-9.]+|dev)$")


def parse_requirements(filename):
    install_requires = []
    dependency_links = []
    for requirement in listify(filename):
        if requirement.startswith("#"):
            continue
        if requirement.startswith("-e"):
            continue
        if requirement.startswith("https:") or requirement.startswith("http:"):
            (_, _, name) = requirement.partition('#egg=')
            ver_match = _SIMPLE_VERSION_RE.match(name)
            if ver_match:
                # egg names with versions need to be converted to
                # an == requirement.
                name = "%(name)s==%(version)s" % ver_match.groupdict()
            install_requires.append(name)
            dependency_links.append(requirement)
        else:
            install_requires.append(requirement)
    return install_requires, dependency_links

install_requires, dependency_links = parse_requirements("requirements.pip")

setup(
    name="vumi-go",
    version="0.0.1",
    url='http://github.com/praekelt/vumi-go',
    license='BSD',
    description="Vumi Go",
    long_description=open('README.rst', 'r').read(),
    author='Praekelt Foundation',
    author_email='dev@praekeltfoundation.org',
    packages=find_packages(),
    install_requires=install_requires,
    dependency_links=dependency_links,
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
