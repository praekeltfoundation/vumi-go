go.vumi.org
===========

Install the dependencies::

    $ virtualenv --no-site-packages ve
    $ source ve/bin/activate
    (ve)$ pip install -r requirements.pip

Other stuff that's required:

* Redis_
* RabbitMQ_, after you've installed this run `sudo ./utils/rabbitmq.setup.sh` to set the correct permissions for the vumi RabbitMQ user.
* Riak_, install as described in: http://wiki.basho.com/Installation.html

After installing Riak_, you will need to edit the /etc/riak/app.config file: set the storage backend to eleveldb instead of bitcask, and enable riak_search.

To ease local development we are using GTalk, you will need at least one GTalk account available to run Vumi Go.

To configure you GTalk addresses, edit the file `config/tagpools.yaml` and find the `xmpp` section and change the lines that say::

    tags:
      - 's.dehaan@gmail.com'

And fill in your available GTalk address(es)::

    tags:
      - 'some-account@gmail.com'

After that, ensure that Redis_ is running and run::

    (ve)$ PYTHONPATH=. python ve/src/vumi/vumi/vumi_tagpools.py -c config/tagpools.yaml create-pool xmpp

This populates Redis_ with the account information Vumi Go needs in order to bind messaging accounts to actual conversations.

Next update the file `config/gtalk_transports.yaml` and replace the 2 `user@xmpp.org` entries whatever GTalk address you are using.

When that's done fire up supervisord::

    (ve)$ supervisord
    (ve)$ supervisorctl status

If everything's running and you've gotten this far then things look good :)

Final steps are:

#. Run `go-admin.sh syncdb --noinput --migrate` to populate the sqlite db for the Django webapp.
#. Run `go-admin.sh go_create_user` and enter the necessary details.
#. Run `go-admin.sh go_assign_tagpool --email-address=... --tagpool=xmpp --max-keys=0`
#. Run `go-admin.sh go_manage_credit --email-address=... --add-credit=1000`
#. Run `go-admin.sh go_manage_application --email-address=... --application-module=go.apps.bulk_message`
#. Run `go-admin.sh go_manage_application --email-address=... --application-module=go.apps.surveys`
#. Use this account to log in at `http://localhost:8000`

.. _Redis: http://redis.io
.. _RabbitMQ: http://rabbitmq.com
.. _Riak: http://wiki.basho.com/Riak.html
