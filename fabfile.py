from fabric.api import *

env.hosts = ['ubuntu@vumi.praekeltfoundation.org']
env.path = '/var/praekelt/vumi/ux'

def deploy():
    with cd(env.path):
        run('git pull')
    