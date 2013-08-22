Available Resources for the Javascript Sandbox
==============================================

The Javascript sandbox provides an isolated environment within which
a developer's (your!) application code is run.

It talks to the outside work via what are called "Resources". These resources
expose core Vumi functionality inside the Sandbox in a controlled fashion.

Applications in Vumi Go's Javascript sandbox have the following resources
available:

**config**

This provides access to the ``config`` variable as stored in the Vumi Go UI.

.. autoclass:: go.apps.jsbox.vumi_app.ConversationConfigResource
   :members:
   :show-inheritance:

**outbound**

This provides access to outbound messaging from the Javascript sandbox to
the end user.

.. autoclass:: go.apps.jsbox.outbound.GoOutboundResource
   :members:
   :show-inheritance:

**metrics**

This provides access to the metrics aggregation system inside Vumi.
Metrics that are fired here are aggregated and available for displaying
in a dashboard. The backend for this is Graphite.

.. autoclass:: go.apps.jsbox.metrics.MetricsResource
   :members:
   :show-inheritance:

**http**

This enables you to make outbound HTTP calls. GET, POST, PUT and DELETE
are available.

.. autoclass:: vumi.application.sandbox.HttpClientResource
   :members:
   :show-inheritance:

**contacts**

This resource provides access to the contact database stored in Vumi Go.
It allows you to create, delete and update contact information.

.. autoclass:: go.apps.jsbox.contacts.ContactsResource
   :members:
   :show-inheritance:

**groups**

This resource provides access to the groups stored in Vumi Go.
It allows you to find, create and update group information and retrieve
their member counts.

.. autoclass:: go.apps.jsbox.contacts.GroupsResource
   :members:
   :show-inheritance:

**log**

Provides logging facilities for your application. These logs are available
for viewing in the UI. The 1000 most recent log entries are stored.

.. autoclass:: go.apps.jsbox.log.GoLoggingResource
   :members:
   :show-inheritance:

**kv**

Provides access to a Redis backed key value store. GET, SET and INCR
operations are available. There is a limit of 10000 keys per user.

.. autoclass:: vumi.application.sandbox.RedisResource
   :members:
   :show-inheritance:
