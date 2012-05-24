from fabric.api import cd, sudo, env

env.hosts = ['ubuntu@vumi.praekelt.com']
env.path = '/var/praekelt/vumi-go'


def deploy():
    with cd(env.path):
        sudo('git pull', user='vumi')


def restart_gunicorn():
    with cd(env.path):
        for i in range(1, 5):
            sudo('. ve/bin/activate && '
                    './ve/bin/supervisorctl restart go:go_%s' % (i,),
                    user='vumi')
