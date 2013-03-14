Vumi Go's HTTP API
==================

The API allows for sending & receiving Vumi messages via HTTP. These messages are plain JSON strings. Two types of messages are available, TransportUserMessages and TransportEvents. These messages can be received via streaming HTTP or can be pushed to 3rd party URL via HTTP POST. Outbound messages & metrics can be pushed to Vumi Go via HTTP PUT.

Each HTTP api is bound to a conversation which stores all of the messages sent & received. HTTP Basic auth is used for authentication, the username is the Vumi Go account key and the password is an access token that is stored in the conversation. In order to connect three keys are required:

	1. The account key
	2. The accesss token
	3. The conversation key


Vumi Messages
-------------

Vumi messages are JSON objects of the following format:

{
	"message_id": "59b37288d8d94e42ab804158bdbf53e5",
	"in_reply_to": null,
	"session_event": null,
    "to_addr": "1234",
    "from_addr": "27761234567",
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

This is the base message format for messages sent & received. A reply to this message would put the value of the "message_id" in the "in_reply_to" field so as to link the two.

The "session_event" field is used for transports that are session oriented, primarily USSD. This field will be either "null", "new", "resume" or "close". There are no guarantees that these will be set for USSD as it depends on the networks whether or not these values are available. If replying to a message in USSD session then set the "session_event" to "resume" if you are expecting a reply back from the user or to "close" if the message you are sending is the last message and the session is to be closed.


Receiving Messages
------------------

GET http://go.vumi.org/api/v1/go/http_api/<conversation-key>/messages.json

If you want messages forwarded to your application with HTTP POST then please supply the URL.

Sending Messages
----------------

PUT http://go.vumi.org/api/v1/go/http_api/<conversation-key>/messages.json

Receiving Events
----------------

GET http://go.vumi.org/api/v1/go/http_api/<conversation-key>/events.json

If you want events forwarded to your application with HTTP POST then please supply the URL.