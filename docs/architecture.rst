.. Vumi Go system architecture

Vumi Go Architecture
====================

.. blockdiag::

   default_group_color = none;

   class "service" [color="#9495ca", linecolor="#5c5e9c", textcolor=black, shape=roundedbox];
   class "persistence" [color="#b6b6c1", linecolor="#58585d", textcolor=black, shape=box];
   class "external" [color="#dfe28e", linecolor="#9b9d71", textcolor=black, shape=box];
   class "gateway" [color="#dfe28e", linecolor="black", textcolor=black, shape=box];

   class "auth" [color=pink, linecolor=red, textcolor=black, shape=ellipse];
   class "django" [color=none, linecolor=black, textcolor=black, shape=box];


   group {
     label = "Outside World";

     // outside
     browser [class="external", label="Person with Browser"];
     api_client [class="external", label="API Client"];
   }

   group {
     label = "HTTP proxies";

     nginx [class="gateway", label="Nginx"];
     haproxy_1 [class="gateway", label="HAproxy"];
     haproxy_2 [class="gateway", label="HAproxy"];
   }

   group {
     // middleware + Django
     auth [class="auth", label="Authentication"];
     django [class="django", label="Django"];
   }

   group {
     label = "Services";

     go_api [class="service", label="Go API", description="Conversations, Routers, Channels & Routing Table"];
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

   browser -> nginx -> haproxy_1 -> django;
   api_client -> nginx -> haproxy_2 -> auth;

   auth -> go_api;

   django -> postgres;

   go_api -> riak;
   go_api -> redis;
   message_store_api -> riak;
   message_store_api -> redis;
   contact_store_api -> riak;
   contact_store_api -> redis;
   tag_pool_api -> riak;
   tag_pool_api -> redis;
   billing_api -> postgres;
