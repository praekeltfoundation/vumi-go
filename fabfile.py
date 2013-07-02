from fabric.api import cd, sudo, env, puts

env.path = '/var/praekelt/vumi-go'


def deploy_go():
    with cd(env.path):
        sudo('git pull', user='vumi')
        sudo("find go -name '*.pyc' -delete")
        _venv_command('./ve/bin/django-admin.py collectstatic --pythonpath=. '
                      '--settings=go.settings --noinput')


def deploy_vumi():
    with cd('%s/ve/src/vumi/' % (env.path,)):
        sudo('git pull', user='vumi')
        sudo("find vumi -name '*.pyc' -delete")


def restart_celery():
    with cd(env.path):
        supervisorctl('restart vumi_celery:celery')


def restart_gunicorn():
    """
    Intentionally restart the gunicorns 1 by 1 so HAProxy is given
    time to load balance across gunicorns that have either already restarted
    or are waiting to be restarted
    """
    with cd(env.path):
        for i in range(1, 5):
            supervisorctl('restart vumi_web:goui_%s' % (i,))


def restart_all(group=None):
    """
    Restart all running processes one-by-one so that the system as a whole
    experiences no down-time during the restart. If a group is specified,
    restart only the processes within that group one by one.
    """
    processes = _supervisorctl_status()
    if group is not None:
        processes = [p for p in processes if p['group'] == group]
    processes = [p for p in processes if p['statename'] == 'RUNNING']
    for p in processes:
        p_name = '%s:%s' % (p['group'], p['name'])
        puts("Restarting %s ..." % (p_name,))
        supervisorctl("restart %s" % p_name)


def deploy_world(restart=True):
    """
    Update Vumi, Vumi Go and the node.js modules and then run restart_all.
    """
    deploy_vumi()
    deploy_go()
    update_nodejs_modules()
    if restart:
        restart_all()


def update_nodejs_modules():
    """
    Update the Node.js modules that the JS sandbox depends on.
    """
    npm_install("vumigo_v01")


def supervisorctl(command):
    return sudo('supervisorctl %s' % (command,))


def npm_install(package):
    return sudo('npm install --global %s' % (package,))


def _venv_command(command, user='vumi'):
    return sudo('. ve/bin/activate && %s' % (command,), user=user)


def _supervisorctl_status():
    status = supervisorctl('status').splitlines()
    processes = []
    for line in status:
        parts = line.split()
        group, _, name = parts[0].partition(':')
        if not name:
            # single processes are in a group with the same
            # name as themselves
            name = group
        processes.append({
            'name': name,
            'group': group,
            'statename': parts[1],
        })
    return processes
