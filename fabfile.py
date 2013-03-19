from fabric.api import cd, sudo, env

env.hosts = ['ubuntu@vumi.praekelt.com']
env.path = '/var/praekelt/vumi-go'


def deploy_go():
    with cd(env.path):
        sudo('git pull', user='vumi')
        _venv_command('./ve/bin/django-admin.py collectstatic --pythonpath=. '
                        '--settings=go.settings --noinput')


def deploy_vumi():
    with cd('%s/ve/src/vumi/' % (env.path,)):
        sudo('git pull', user='vumi')


def restart_celery():
    with cd(env.path):
        supervisorctl('restart vumi_web:celery')


def restart_gunicorn():
    """
    Intentionally restart the gunicorns 1 by 1 so HAProxy is given
    time to load balance across gunicorns that have either already restarted
    or are waiting to be restarted
    """
    with cd(env.path):
        for i in range(1, 5):
            supervisorctl('restart vumi_web:goui_%s' % (i,))


def supervisorctl(command):
    return sudo('supervisorctl %s' % (command,))


def _venv_command(command, user='vumi'):
    return sudo('. ve/bin/activate && %s' % (command,), user=user)
