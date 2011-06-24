from fabric.api import *

env.key_filename = '/Users/sdehaan/.ssh/praekelt_foundation_eu.pem'
env.hosts = ['ubuntu@vumi.praekeltfoundation.org']
env.path = '/var/praekelt/vumi/ux'

def deploy():
    with cd(env.path):
        run('git pull')
    