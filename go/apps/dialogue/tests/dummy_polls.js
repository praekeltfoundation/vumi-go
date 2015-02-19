var simple_poll = {
    conversation_key: "conversation-key",
    start_state: {uuid: "choice-1"},
    poll_metadata: {
        repeatable: true,
    },
    channel_types: [{
        name: 'twitter',
        label: 'Twitter'
    }, {
        name: 'sms',
        label: 'SMS'
    }],
    states: [
    {
        // these are common to all state types
        uuid: "choice-1", // name is unique
        name: "Message 1", // a friendly name for the user to see
        store_as: "message-1",
        type: "choice", // menu of options
        entry_endpoint: null, // null for the start state
        store_on_contact: true,
        // choice specific
        text: "What is your favourite colour?",
        choice_endpoints: [ // these are actually also the endpoints
        {value: "value-1", label: "Red", uuid: "endpoint-1"},
        {value: "value-2", label: "Blue", uuid: "endpoint-2"},
        {value: "value-3", label: "Green", uuid: "endpoint-3"},
        {value: "value-4", label: "Black", uuid: "endpoint-11"},
        {value: "value-5", label: "Yellow", uuid: "endpoint-14"}
        ]
    },
    {
        uuid: "group-1",
        name: "Message 2",
        type: "group",
        group: {key: 'group-1'},
        entry_endpoint: {uuid: "endpoint-4"},
        exit_endpoint: {uuid: "endpoint-5"}
    },
    {
        uuid: "send-1",
        name: "Message 3",
        type: "send",
        text: "Hello over other endpoint",
        channel_type: "twitter",
        entry_endpoint: {uuid: "endpoint-6"},
        exit_endpoint: {uuid: "endpoint-7"}
    },
    {
        uuid: "freetext-1",
        name: "Message 3",
        store_as: "message-3",
        type: "freetext",
        store_on_contact: true,
        entry_endpoint: {uuid: "endpoint-8"},
        // freetext specific
        exit_endpoint: {uuid: "endpoint-9"},
        text: "What is your name?"
    },
    {
        uuid: "end-1",
        name: "Ending 1",
        store_as: "ending-1",
        type: "end",
        store_on_contact: true,
        entry_endpoint: {uuid: "endpoint-10"},
        // end specific
        text: "Thank you for taking our survey"
    },
    {
        uuid: "http_json-1",
        name: "json post 1",
        type: "httpjson",
        url: "www.foo.bar",
        method: "GET",
        entry_endpoint: {uuid: "endpoint-12"},
        exit_endpoint: {uuid: "endpoint-13"}
    },
    {
        uuid: "http_json-2",
        name: "json post 2",
        type: "httpjson",
        url: "www.foo.bar",
        method: "POST",
        entry_endpoint: {uuid: "endpoint-15"},
        exit_endpoint: {uuid: "endpoint-16"}
    }],
    connections: [
    {
        source: {uuid: "endpoint-1"},
        target: {uuid: "endpoint-4"}
    },
    {
        source: {uuid: "endpoint-2"},
        target: {uuid: "endpoint-10"}
    },
    {
        source: {uuid: "endpoint-3"},
        target: {uuid: "endpoint-6"}
    },
    {
        source: {uuid: "endpoint-5"},
        target: {uuid: "endpoint-8"}
    },
    {
        source: {uuid: "endpoint-7"},
        target: {uuid: "endpoint-8"}
    },
    {
        source: {uuid: "endpoint-9"},
        target: {uuid: "endpoint-10"}
    },
    {
        source: {uuid: "endpoint-11"},
        target: {uuid: "endpoint-12"}
    },
    {
        source: {uuid: "endpoint-13"},
        target: {uuid: "endpoint-10"}
    },
    {
        source: {uuid: "endpoint-14"},
        target: {uuid: "endpoint-15"}
    },
    {
        source: {uuid: "endpoint-16"},
        target: {uuid: "endpoint-10"}
    }]
};


// export
this.simple_poll = simple_poll;
