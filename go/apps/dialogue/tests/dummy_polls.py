def simple_poll():
    return {
        "conversation": "conversation-key",
        "start_state": {"uuid": "choice-1"},
        "poll_metadata": {
            "repeatable": True,
            'delivery_class': 'ussd'
        },
        'channel_types': [],
        "states": [
            {
                # these are common to all state types
                "uuid": "choice-1",  # name is unique
                "name": "Message 1",  # a friendly name for the user to see
                "store_as": "message-1",
                "type": "choice",  # menu of options
                "entry_endpoint": None,  # null for the start state
                # choice specific
                "text": "What is your favourite colour?",
                "choice_endpoints": [  # these are actually also the endpoints
                    {"value": "value-1", "label": "Red", "uuid": "endpoint-1"},
                    {"value": "value-2", "label": "Blue", "uuid": "endpoint-2"}
                ],
            },
            {
                "uuid": "freetext-1",
                "name": "Message 2",
                "store_as": "message-2",
                "type": "freetext",
                "entry_endpoint": {"uuid": "endpoint-3"},
                # freetext specific
                "exit_endpoint": {"uuid": "endpoint-4"},
                "text": "What is your name?",
            },
            {
                "uuid": "end-1",
                "name": "Ending 1",
                "store_as": "ending-1",
                "type": "end",
                "entry_endpoint": {"uuid": "endpoint-5"},
                # end specific
                "text": "Thank you for taking our survey",
            },
        ],
        "connections": [
            {
                "source": {"uuid": "endpoint-1"},
                "target": {"uuid": "endpoint-3"},
            },
            {
                "source": {"uuid": "endpoint-2"},
                "target": {"uuid": "endpoint-5"}
            },
            {
                "source": {"uuid": "endpoint-4"},
                "target": {"uuid": "endpoint-5"}
            },
        ],
    }
