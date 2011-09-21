from fabric.api import *


env.hosts = ['ubuntu@cloud.praekeltfoundation.org']
env.path = '/var/praekelt/go'


def deploy():
    with cd(env.path):
        run('git pull')
        run('ve/bin/supervisorctl -c config/supervisord.conf restart all')
