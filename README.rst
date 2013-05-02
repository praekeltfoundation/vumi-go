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

To start some sample conversations such as Wikipedia execute the
following command::

    (ve)$ ./setup_env/build/go_startup_env.sh

Next start everything using Supervisord_::

    (ve)$ supervisord -c setup_env/build/go_supervisord.conf
    (ve)$ supervisorctl -c setup_env/build/go_supervisord.conf

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

.. _Redis: http://redis.io
.. _RabbitMQ: http://rabbitmq.com
.. _Riak: http://wiki.basho.com/Riak.html
.. _Vumi: https://github.com/praekelt/vumi
.. _Supervisord: http://www.supervisord.org
