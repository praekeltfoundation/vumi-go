go.vumi.org
===========

Install the dependencies::

    $ virtualenv --no-site-packages ve
    $ source ve/bin/activate
    (ve)$ pip install -r requirements.pip

Other stuff that's required:

    * Redis_
    * RabbitMQ_, after you've installed this run `sudo ./ve/src/vumi/utils/rabbitmq.setup.sh` to set the correct permissions for the vumi RabbitMQ user.

To ease local development we are using GTalk, you will need at least one GTalk account available to run Vumi Go.

To configure you GTalk addresses, edit the file `go/conversation/management/commands/go_populate_messaging_tags.py` and change the line that says::

    ("gtalk", ["go-%d@vumi.org" % i for i in range(1, 1 + 5)]),

And fill in your available GTalk addresses::

    ("gtalk", ["some-account1@gmail.com"]),

After that, ensure that Redis_ is running and run::

    (ve)$ ./go-admin.sh go_populate_messaging_tags --gtalk

This populates Redis_ with the account information Vumi Go needs in order to bind messaging accounts to actual conversations.

Next update the file `config/gtalk_transports.yaml` and replace the `some-account1@gmail.com` on lines 9 and 19 which whatever GTalk address you are using.

When that's done fire up supervisord::

    (ve)$ supervisord
    (ve)$ supervisorctl status
    celery                           RUNNING    pid 12380, uptime 0:07:32
    dispatcher                       RUNNING    pid 12383, uptime 0:07:32
    go                               RUNNING    pid 12419, uptime 0:04:41
    poll_application                 RUNNING    pid 12377, uptime 0:07:33
    smpp_transport:smpp_transport_0  RUNNING    pid 12382, uptime 0:07:32
    vumiapi_worker:vumiapi_worker_0  RUNNING    pid 12376, uptime 0:07:33
    vumigo_gtalk_transports:vumigo_gtalk_transports_0 RUNNING    pid 12378, uptime 0:07:33
    vumigo_router:vumigo_router_0    RUNNING    pid 12379, uptime 0:07:33

If you've gotten this far then things look good :)

Final steps are:

1. Create the PostgreSQL user for `go` with password `go` and create a database called `go`.
2. Run `go-admin.sh syncdb --noinput --migrate` to populate the db.
3. Run `go-admin.sh createsuperuser` to create a superuser.
4. Run `go-admin.sh runserver` to run the dev-server and login at `http://localhost:8000/admin/` with your super-user credentials.
5. Create a normal Django user but specify an email address as the `username`.
6. Use this account to log in at `http://localhost:8000`

.. _Redis: http://redis.io
.. _RabbitMQ: http://rabbitmq.com