# Getting started with vumi-go

Author: [Mike Jones](mike@westerncapelabs.com)  
All bad practices and advice is entirely the fault of the author

These notes are in addition to [these](https://github.com/praekelt/vumi-go/blob/develop/README.rst)

## Source

Github [repo](https://github.com/praekelt/vumi-go)

## Environment

Use Vagrant for sanity. [Getting Started](http://docs.vagrantup.com/v1/docs/getting-started/index.html)

Use the [precise64.box](http://files.vagrantup.com/precise64.box) (323MB)

Vagrantfile [here](https://gist.github.com/imsickofmaps/3aca802406e6bc4ba278)

Chef scripts [here](https://gist.github.com/imsickofmaps/5144946)

Riak config changes [here](https://gist.github.com/imsickofmaps/5145116)

## Vumi-go Install

Connect to your vagrant environment using `vagrant ssh`

Go to the mapped vumi-go folder root (`/srv/vumi-go` if you used Vagrantfile above)

Run:

    $ virtualenv --no-site-packages ve
    $ source ve/bin/activate
    (ve)$ pip install -r requirements.pip

## Vumi setup

Vumi needs access to rabbitmq and there's a nice little helper script for you (read the source before sudoing for security):

    (ve)$ sudo ./ve/src/vumi/utils/rabbitmq.setup.sh

## Vumi-go Configs

Base configs can be found [here](https://gist.github.com/smn/e2c1bded79a961b6c450)

Copy them to `local-config` (which you'll need to create):

Next update the file `local-config/gtalk_transports.yaml` and replace the 2 user@xmpp.org entries with whatever GTalk address you are using.

Create `etc` in the root and copy across `supervisord.conf`

## Start-up

Ensure that Redis is running and run:

    (ve)$ PYTHONPATH=. python ve/src/vumi/vumi/scripts/vumi_tagpools.py -c config/tagpools.yaml create-pool xmpp

This populates Redis with the account information Vumi Go needs in order to bind messaging accounts to actual conversations.

When that's done fire up supervisord:

    (ve)$ supervisord 
    (ve)$ supervisorctl status


Final config:

Populate the sqlite db for the Django webapp:

    (ve)$ ./go-admin.sh syncdb --noinput --migrate 
    
Create user and enter the necessary details (Name is just first name):

    (ve)$ ./go-admin.sh go_create_user
    
Use the email address to associate with xmpp account:

    (ve)$ ./go-admin.sh go_assign_tagpool --email-address=<email of account created> --tagpool=xmpp --max-keys=0

Give yourself some credit:

    (ve)$ ./go-admin.sh go_manage_credit --email-address=<email of account created> --add-credit=1000

Grant yourself application permissions:

    (ve)$ ./go-admin.sh go_manage_application --email-address=<email of account created> --application-module=go.apps.bulk_message --enable 
    (ve)$ ./go-admin.sh go_manage_application --email-address=<email of account created> --application-module=go.apps.surveys --enable

Fire up this bad boy:

    (ve)$ ./go-admin.sh runserver [::]:8000
    (ve)$ supervisorctl start all

## Go go go!

Log in at [http://localhost:8000](http://localhost:8000)


## Debugging

Run `tail` on files in `./logs/ ... look at .err and .log because sometimes errors are in .log :grin:
