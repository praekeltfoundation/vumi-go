Vumi Go
=======

Documentation available online at http://vumi-go.readthedocs.org/ and in the `docs` directory of the repository.

|vumigo-ci|_ |vumigo-cover|_ |vumigo-waffle|_

.. |vumigo-ci| image:: https://travis-ci.org/praekelt/vumi-go.png?branch=develop
.. _vumigo-ci: https://travis-ci.org/praekelt/vumi-go

.. |vumigo-cover| image:: https://coveralls.io/repos/praekelt/vumi-go/badge.png?branch=develop
.. _vumigo-cover: https://coveralls.io/r/praekelt/vumi-go

.. |vumigo-waffle| image:: https://badge.waffle.io/praekelt/vumi-go.png?label=ready
.. _vumigo-waffle: https://waffle.io/praekelt/vumi-go


Installing
~~~~~~~~~~

Install the dependencies::

    $ virtualenv --no-site-packages ve
    $ source ve/bin/activate
    (ve)$ pip install -r requirements.pip

Other stuff that's required:

* Redis_
* RabbitMQ_, after you've installed this run `sudo ./utils/rabbitmq.setup.sh` to set the correct permissions for the vumi RabbitMQ user.
* Riak_, install as described in: http://wiki.basho.com/Installation.html

After installing Riak_, you will need to edit the `/etc/riak/app.config` file: set the storage backend to `eleveldb` instead of `bitcask`, and enable `riak_search`.

.. note::
    There is a Vagrantfile in the Vumi_ repository that can be used for Vumi Go as well.


Bootstrapping a development environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After having installed the dependencies with pip and ensuring that Redis_,
Riak_ and RabbitMQ_ are running execute the following command:

::

    (ve)$ ./setup_env.sh

This will generate all the necessary config files for running a set of
standard applications and Telnet transports emulating a USSD and SMS
connection.

If this is your first time bootstrapping the dev environment, you'll also need
to create the RabbitMQ vhost used by the local dev environment (you may need to
put ``sudo`` on the front of these commands)::

    (ve)$ rabbitmqctl add_vhost /develop
    (ve)$ rabbitmqctl set_permissions -p /develop vumi '.*' '.*' '.*'

You'll also need to provide some extra Django config. Create a
``production_settings.py`` file in ``/path/to/repo/go/`` (next to the existing
``settings.py`` file) containing that following::

    from go.base import amqp

    amqp.connect('librabbitmq://vumi:vumi@localhost//develop')

    SECRET_KEY = 'hello'

Next start everything using Supervisord_::

    (ve)$ supervisord -c setup_env/build/go_supervisord.conf

You can manage the running processes with the following command::

    (ve)$ supervisorctl -c setup_env/build/go_supervisord.conf

With everything running, complete the setup by running the generated setup
script::

    (ve)$ ./setup_env/build/go_startup_env.sh

Now you should be able to login to the Vumi UI at http://localhost:8000 using
the account details as specified in `setup_env/accounts.yaml`.

The default accounts created are:

================= ==========
    Username       Password
================= ==========
user1@example.org password
user2@example.org password
================= ==========

By default the Wikipedia USSD service is configured to be running on
localhost 8081.

::

    $ telnet localhost 8081
    Trying 127.0.0.1...
    Connected to localhost.
    Escape character is '^]'.
    Please provide "to_addr":
    *120*10001#
    Please provide "from_addr":
    simon
    [Sending all messages to: *120*10001# and from: simon]
    What would you like to search Wikipedia for?
    ...

The SMS delivery part uses 'longcode-10001' as the virtual address and
the outbound SMSes as part of the USSD Wikipedia are sent to that address.


Using GTalk as a transport for testing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To ease local development we often use GTalk. You will need at least two
Gtalk addresses, one will be used for the Vumi transport the other you
will need to use with your normal Gtalk client to interact with the service.

Start the XMPP transport with the following command::

    (ve)$ twistd -n vumi_worker \
    >      --worker-class=vumi.transports.xmpp.XMPPTransport
    >      --config=path/to/xmpp-config.yaml

The configuration for the XMPP transport should have the following parameters::

    transport_name: <desired transport name> # change this
    username: <your username> # change this
    password: <your password> # change this
    host: talk.google.com
    port: 5222
    status: chat
    status_message: Vumi Go!

    middleware:
        - logging_mw: vumi.middleware.logging.LoggingMiddleware
        - gtalk_tagging_mw: vumi.middleware.tagger.TaggingMiddleware

    logging_mw:
        log_level: debug

    gtalk_tagging_mw:
       incoming:
         addr_pattern: '^(.+\@.+)/?.*$'
         tagpool_template: 'xmpp'
         tagname_template: '\1'
       outgoing:
         tagname_pattern: '.*'
         msg_template: {}

For you to be able to use this account for messaging you will need to add
it to the `tagpools.yaml` file. Do this by adding the following below
`ussd_tagpool` under `pools`::

    xmpp_tagpool:
      tags:
        - xmpp@example.org # change this
      metadata:
        display_name: "Google Talk"
        delivery_class: gtalk
        transport_type: xmpp
        user_selects_tag: true
        server_initiated: true
        client_initiated: true
        transport_name: <name of your transport> # change this
        msg_options: {}

Next update the Tagpool Manager with this new configuration::

    (ve)$ ./go-admin.sh go_setup_env \
            --config-file=./setup_env/config.yaml \
            --tagpool-file=./setup_env/tagpools.yaml

And give your account access to this new tagpool::

    (ve)$ ./go-admin go_assign_tagpool \
            --email-address=user1@example.org \
            --tagpool=xmpp_tagpool \
            --max-keys=0

.. _Redis: http://redis.io
.. _RabbitMQ: http://rabbitmq.com
.. _Riak: http://wiki.basho.com/Riak.html
.. _Vumi: https://github.com/praekelt/vumi
.. _Supervisord: http://www.supervisord.org
