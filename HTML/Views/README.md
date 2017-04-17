Vumi Campaign Bulder Tool
==============

The tool currently reads file at ../../js/data/example.json. This will be replaced with configurable API endpoint later. 

It needs work on:
- Edit and Save, including logic for handling changes to the plumbing. 
- Fixing a couple of jsPlumb quirks.
- Interface tweaks (drag to edges scrolling, snap to grid...)
- Handling of attempts to produce invalid graphs (e.g. one-node loops).

The JSON data format for loading/saving is below. 
This object represents the campaign flow as a directed graph. Node "type" (one option/own text/no input) is determined based on the outgoing connections ("tails"). 
When GETting from server, "id" fields are the server-internal IDs for the nodes. When PUTting to the server, they will have been made client-internal. 
With this method, the entire graph will need to be overwritten on save. 


```
	"nodes": [
		{
			"id": 123,								// ID for the node. 
			"position": [0,0],						// [x, y] position of widget on canvas (for display purposes only).
			"message": "Are you sure?",				// String that is shown to user
			"tails": [								// Array of outgoing connections to other nodes. Represented in app as options in response to the message. 
				{
					"node_id": 48,					// ID of node connected to by this edge
					"text": "Yes"					// String shown to user for this out option
				},
				{
					"node_id": 99,
					"text": "Yes maybe"
				}
			]
		},
		{
			"id": 99,
			"position": [1,0],
			"message": "How sure?",
			"tails": [								
				{
					"node_id": 48,
					"text": null					// When a tail has undefined or null text, the app represents it as an option for user to supply own answer. Max one such tail per node. 
				}
			]
		},
		{
			"id": 48,
			"position": [1,1],
			"type": "message",
			"message": "Thank you for being sure.",
			"tails": null							// Null value represents termination of graph. (An empty array here would indicate an incomplete graph.)
		}
	]
```