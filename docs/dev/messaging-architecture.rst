.. Vumi Go messaging architecture

Vumi Go Messaging Architecture
==============================

.. blockdiag::

   default_group_color = none;

   // node styles

   class "transport" [color="#9495ca", linecolor="#5c5e9c", textcolor=black, shape=roundedbox];
   class "routing" [color="#b6b6c1", linecolor="#58585d", textcolor=black, shape=box];
   class "external" [color="#dfe28e", linecolor="#9b9d71", textcolor=black, shape=box];
   class "conversation" [color="#dfe28e", linecolor="black", textcolor=black, shape=box];
   class "router" [color="#dfe28e", linecolor="black", textcolor=black, shape=box];

   class "metrics" [color=none, linecolor=black, textcolor=black, shape=box];
   class "commands" [color=none, linecolor=black, textcolor=black, shape=box];

   // edge styles

   class "rabbit" [color=black];
   class "rabbit_command" [color=blue, style=dotted];
   class "http" [color=black, style=dotted];
   class "other" [color=grey];

   // nodes

   group {
     label = "Outside World";

     cellphone [class="external", label="Person\nwith Phone"];
     tablet [class="external", label="Person\nwith Tablet"];

     cellphone_network [class="external", label="Cellphone Network"];
     mxit [class="external", label="Mxit"];
     twitter [class="external", label="Twitter"];
     gchat [class="external", label="Google Chat"];
   }

   group {
     label = "Transports";

     sms_transport [class="transport", label="SMS\ntransport"];
     mxit_transport [class="transport", label="Mxit\ntransport"];
     twitter_transport [class="transport", label="Twitter\ntransport"];
     gchat_transport [class="transport", label="XMPP\ntransport"];
   }

   group {
     label = "Routing & Billing";
     orientation = portrait;

     billing_api [class="routing", label="Billing API"];
     billing [class="routing", label="Billing\nWorker"];
     rtd [class="routing", label="RTD\n(Routing Table)", stacked];
   }

   group {
     label = "Workers";

     routers [class="router", label="Routers", stacked];
     conversations [class="conversation", label="Conversation\nWorkers", stacked];
   }

   group {
     label = "Controllers";

     metrics [class="metrics", label="Metrics Worker"];
     commands [class="commands", label="Command\nDispatcher"];
   }

   // edges

   cellphone <-> cellphone_network [class="other"];
   cellphone <-> mxit [class="other"];
   tablet <-> twitter [class="other"];
   tablet <-> gchat [class="other"];

   cellphone_network <-> sms_transport [class="other"];
   mxit <-> mxit_transport [class="other"];
   twitter <-> twitter_transport [class="other"];
   gchat <-> gchat_transport [class="other"];

   sms_transport <-> rtd [class="rabbit"];
   mxit_transport <-> rtd [class="rabbit"];
   twitter_transport <-> rtd [class="rabbit"];
   gchat_transport <-> rtd [class="rabbit"];

   billing_api <- billing [class="http"];
   billing <-> rtd [class="rabbit"];

   rtd <-> routers [class="rabbit"];
   rtd <-> conversations [class="rabbit"];

   commands, metrics -> routers [class="rabbit_command"];
   conversations <- commands, metrics [class="rabbit_command"];
