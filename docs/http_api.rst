.. _http_api:

Vumi Go's HTTP API
==================

The API allows for sending & receiving Vumi messages via HTTP. These
messages are plain JSON strings. Three types of messages are available:

 * Inbound and outbound user messages (e.g. SMSes, USSD responses,
   Twitter messages)
 * Events (e.g. delivery reports, acknowledgements)
 * Metrics (values recorded at a specific time)

Inbound user messages and events can be received via streaming HTTP or
can be pushed to a third party URL via HTTP POST.  Outbound messages and
metrics can be pushed to Vumi Go via HTTP PUT.

Each HTTP api is bound to a conversation which stores all of the
messages sent and received. HTTP Basic auth is used for
authentication, the username is the Vumi Go account key and the
password is an access token that is stored in the conversation. In
order to connect three keys are required:

1. The account key
2. The accesss token
3. The conversation key


Inbound and Outbound User Messages
----------------------------------

This is the format for messages being sent to, or received from, a
person.

User messages are JSON objects of the following format:

.. code-block:: javascript

    {
        "message_id": "59b37288d8d94e42ab804158bdbf53e5",
        "in_reply_to": null,
        "session_event": null,
        "to_addr": "1234",
        "to_addr_type": "msisdn",
        "from_addr": "27761234567",
        "from_addr_type": "msisdn",
        "content": "This is an incoming SMS!",
        "transport_name": "smpp_transport",
        "transport_type": "sms",
        "transport_metadata": {
            // this is a dictionary containing
            // transport specific data
        },
        "helper_metadata": {
            // this is a dictionary containing
            // application specific data
        }
    }

A reply to this message would put the value of the "message_id" in the
"in_reply_to" field so as to link the two.

The `from_addr_type` and `to_addr_type` fields describe the type of address
declared in `from_addr` and `to_addr`. The default for `to_addr_type` is
`msisdn`, and the default for `from_addr_type` is `null`, which is used to
mark that the type is unspecified. The other valid values are `irc_nickname`,
`twitter_handle`, `gtalk_id`, `jabber_id`, `mxit_id`, and `wechat_id`.

The "session_event" field is used for transports that are session oriented,
primarily USSD. This field will be either "null", "new", "resume" or "close".
There are no guarantees that these will be set for USSD as it depends on
the networks whether or not these values are available. If replying to a
message in USSD session then set the "session_event" to "resume" if you are
expecting a reply back from the user or to "close" if the message you are
sending is the last message and the session is to be closed.

The `go-heroku <https://github.com/smn/go-heroku/>`_ application is an
example app that uses the HTTP API to receive and send messages.

A Python client for the HTTP API is available at
https://github.com/praekelt/go-http-api. It can be installed with
``pip install go-http``.


Sending Messages
----------------

.. code-block:: bash

    $ curl -X PUT \
           --user '<account-key>:<access-token>' \
           --data '{"in_reply_to": "59b37288d8d94e42ab804158bdbf53e5", \
                    "to_addr": "27761234567", \
                    "to_addr_type": "msisdn", \
                    "content": "This is an outgoing SMS!"}' \
           http://go.vumi.org/api/v1/go/http_api_nostream/<conversation-key>/messages.json \
           -vvv

The UI expects you to specify an access token. All requests to the API
require you to use your account key as the username and the token as the
password.

The response to the PUT request is the complete Vumi Go user message
and includes the generated Vumi ``message_id`` which should be stored
if you wish to be able to associate events with the message later.

If a message is sent to a recipient that has opted out, the response will be an
HTTP 400 error, with the body detailing that the recipient has opted out.
Messages sent as a reply will still go through to an opted out recipient. The
following is an example response of the error returned by the API:

.. code-block:: javascript

    {
        "success": false,
        "reason": "Recipient with msisdn +12345 has opted out"
    }

This behaviour can be overridden by setting the `disable_optout` flag in the
account to `True`. Ask a Vumi Go admin if you need to have optouts disabled.


Receiving User Messages
-----------------------

Vumi Go will forward any inbound messages to your application via an
HTTP POST. Please specify the URL in the Go UI. You can include a
username and password in the URL and use HTTPS if you require
authentication.

There is a separate URL for receiving events.


Events
------

This is the format for events. Each event is associated with an
outbound user message.

Events are JSON messages with the following format:

.. code-block:: javascript

    {
        "message_type": "event",
        "event_id": "b04ec322fc1c4819bc3f28e6e0c69de6",
        "event_type": "ack",
        "user_message_id": "60c48289d8d94e42ab804159acce42d4",
        "helper_metadata": {
            // this is a dictionary containing
            // application specific data
        },
        "timestamp": "2014-10-28 16:19:37.485612",
        "sent_message_id": "external-id",
    }


The ``event_id`` unique id for this event.

The ``user_message_id`` is the id of the outbound message the event is
for (this should be returned to you when you post the message to the
HTTP API).

The ``event_type`` is the type of event and can be either ``ack``,
``nack`` or ``delivery_report``.

An ``ack`` indicates that the outbound message was succesfully sent to
a third party (e.g. a cellphone network operator) for sending. A
``nack`` indicates that the message was not successfully sent to a
third party and should be resent. The reason the message could not be
sent will be given in the ``nack_reason`` field. Every outbound
message should receive either an ``ack`` or a ``nack`` event.

A ``delivery_report`` indicates whether a message has successfully
reached it's final destination (e.g. a cellphone). Delivery reports
are only available for some SMS channels. The delivery status will be
given in the ``delivery_status`` field and can be one of ``pending``
(SMS is still waiting to be delivered to the cellphone), ``failed``
(the cellphone operator has given up attempting to deliver the SMS) or
``delivered`` (the SMS was successfully delivered to the cellphone).

.. note::

   The meaning of delivery statuses can vary subtly between cellphone
   operators and should not be relied upon without careful testing of
   your specific use case.


Receiving Events
----------------

Vumi Go will forward any events to your application via an HTTP
POST. Please specify the URL in the Go UI. You can include a username
and password in the URL and use HTTPS if you require authentication.

This is a separate URL to the one for receiving user messages.


Publishing Metrics
------------------

You are able to publish metrics to Vumi Go via the HTTP APIs metrics endpoint.
These metrics are able to be displayed in the Vumi GO UI using the dashboards.

How these dashboards are configured is explained in :ref:`dashboards`.

::

    PUT http://go.vumi.org/api/v1/go/http_api_nostream/<conversation-key>/metrics.json

An example using curl from the commandline:

.. code-block:: bash

    $ curl -X PUT \
        --user '<account-key>:<access-token>' \
        --data '[["total_pings", 1200, "MAX"]]' \
        https://go.vumi.org/api/v1/go/http_api_nostream/<conversation-key>/metrics.json \
        -vvv
