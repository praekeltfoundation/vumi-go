Example Code for Javascript Sandbox features
============================================

The way the Javascript sandbox talks to the outside world can sometimes
be a bit un-intuitive when first starting with Vumi Go development.

Here are some code samples to give you a head start:

Using the Key-Value store:
~~~~~~~~~~~~~~~~~~~~~~~~~~

The KV store allows for GET, SET and INCR operations.
These are namespaced to your account unless you explicitly namespace
it differently per conversation. This allows you to share counters
across different applications.

If you're looking for DECR just use INCR with a negative value.

https://github.com/smn/go-kv-store


Firing Events from an Application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Metrics are crucial for any application. Our metrics backend is powered
by Graphite and your application can send metrics to Graphite for aggregation.

The metrics are not yet visible within the UI but hopefully will be graphed
there soon.

https://github.com/smn/go-events-firing


Using the HTTP API
~~~~~~~~~~~~~~~~~~

The HTTP API allows for interacting with 3rd party applications that are
not hosted on our platform. It allows for both streaming of messages in
real time or using HTTP POST to forward message (and message events) to
a remote URL.

Django backend for HTTP forwarding setup:
    https://github.com/smn/go-heroku

Node.js backend for consuming the Streaming API:
    https://github.com/smn/go-heroku-streaming
