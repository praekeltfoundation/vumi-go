.. Vumi Go system architecture

Vumi Go Architecture
====================

.. blockdiag::

   default_group_color = none;

   // node styles

   class "service" [color="#9495ca", linecolor="#5c5e9c", textcolor=black, shape=roundedbox];
   class "persistence" [color="#b6b6c1", linecolor="#58585d", textcolor=black, shape=box];
   class "external" [color="#dfe28e", linecolor="#9b9d71", textcolor=black, shape=box];
   class "gateway" [color="#dfe28e", linecolor="black", textcolor=black, shape=box];

   class "auth" [color=pink, linecolor=red, textcolor=black, shape=ellipse];
   class "django" [color=none, linecolor=black, textcolor=black, shape=box];

   // edge styles

   class "to_postgres" [color=lightgrey];
   class "to_riak" [color=black];
   class "to_redis" [color=black, style=dotted];

   // nodes

   group {
     label = "Outside World";

     // outside
     browser [class="external", label="Person\nwith Browser"];
     api_client [class="external", label="API Client"];
   }

   group {
     label = "HTTP proxies";

     nginx [class="gateway", label="Nginx"];
     nginx_redirect [class="gateway", label="Nginx internal\nredirect", color="#FFFFFF"];
     haproxy_1 [class="gateway", label="HAproxy"];
     haproxy_2 [class="gateway", label="HAproxy"];
   }

   group {
     // middleware + Django
     auth [class="auth", label="Authentication"];
     django [class="django", label="Django ☢"];
     generic_service [class="service", shape="dots"];
   }

   group {
     label = "Services";

     go_api [class="service", label="Go API ☢", description="Conversations, Routers, Channels & Routing Table"];
     message_store_api [class="service", label="Message Store API"];
     contact_store_api [class="service", label="Contact Store API"];
     tag_pool_api [class="service", label="Tag Pool API"];
     billing_api [class="service", label="Billing API"];
   }

   group {
     label = "Persistence";

     postgres [class="persistence", label="Postgres"];
     riak [class="persistence", label="Riak"];
     redis [class="persistence", label="Redis"];
   }

   // edges

   browser -> nginx -> haproxy_1 -> auth;
   api_client -> nginx -> haproxy_2 -> django;

   auth -> go_api;

   django -> postgres [class="to_postgres"];
   billing_api -> postgres [class="to_postgres"];

   go_api -> riak [class="to_riak"];
   go_api -> redis [class="to_redis"];
   message_store_api -> riak [class="to_riak"];
   message_store_api -> redis [class="to_redis"];
   contact_store_api -> riak [class="to_riak"];
   contact_store_api -> redis [class="to_redis"];
   tag_pool_api -> riak [class="to_riak"];
   tag_pool_api -> redis [class="to_redis"];

   django -> nginx_redirect -> generic_service;


Notes
-----

  * ☢ indicates that a component requires requests to be
    authenticated (i.e. it is intended to be exposed as a public service).

  * Public services are expected to use Nginx internal redirects
    to return results of specific requests to internal services as needed.
