var vumigo = require("vumigo_v01");
var jed = require("jed");

if (typeof api === "undefined") {
    // testing hook (supplies api when it is not passed in by the real sandbox)
    var api = this.api = new vumigo.dummy_api.DummyApi();
}

var Promise = vumigo.promise.Promise;
var success = vumigo.promise.success;
var Choice = vumigo.states.Choice;
var ChoiceState = vumigo.states.ChoiceState;
var FreeText = vumigo.states.FreeText;
var EndState = vumigo.states.EndState;
var InteractionMachine = vumigo.state_machine.InteractionMachine;
var StateCreator = vumigo.state_machine.StateCreator;

function DialogueStateCreator() {
    var self = this;

    StateCreator.call(self, null); // start_state is set in on_config_read
    self.poll = null;  // poll is set in on_config_read

    self.on_config_read = function(event) {
        self.poll = event.config.poll || {};
        var states = poll.states || [];
        self.start_state = states[0].uuid;
        states.forEach(function(state_description) {
            self.add_creator(state.uuid,
                             self.mk_state_creator(state_description));
        });
    };

    self.get_connection = function(source) {
        var connections = self.poll.connections.filter(
            function (c) { return (c.source.uuid === source); });
        if (connections.length !== 1) {
            return null;
        }
        return connections[0];
    };

    self.get_state_by_entry_endpoint = function(endpoint) {
        var states = self.poll.states.filter(
            function (s) { return (s.entry_endpoint == endpoint); });
        if (states.length !== 1) {
            return null;
        }
        return states[0].uuid;
    };

    self.get_next_state = function(source) {
        var connection = self.get_connection(source);
        if (connection === null) {
            return null;
        }
        return self.get_state_by_entry_endpoint(connection.endpoint.uuid);
    };

    self.mk_state_creator = function(state_description) {
        return function(state_name, im) {
            return self.generic_state_creator(state_name, im, state_description);
        };
    };

    self.generic_state_creator = function(state_name, im, state_description) {
        var creator = self[state_description.type + '_state_creator'];
        if (typeof handler === 'undefined') {
            handler = self.unknown_state_creator;
        }
        return handler(state_name, im, state_description);
    };

    self.choice_state_creator = function(state_name, im, state_description) {
        var choices = state_description.choice_endpoints.map(
            function (c) { return new Choice(c.value, c.label); });
        return new ChoiceState(
            state_name,
            function (choice) {
                var endpoints = state_description.choice_endpoints.filter(
                    function (c) { return (c.value == choice.value); });
                if (endpoints.length !== 1) {
                    return state_name;
                }
                return self.get_next_state(endpoints[0].uuid);
            },
            state_description.text,
            choices
        );
    };

    self.freetext_state_creator = function(state_name, im, state_description) {
        return new FreeText(
            state_name,
            function (content) {
                return self.get_next_state(state_description.exit_endpoint);
            },
            state_description.text
        );
    };

    self.end_state_creator = function(state_name, im, state_description) {
        var next_state = null;
        if (self.get_metadata('repeatable')) {
            next_state = self.start_state;
        }
        return new EndState(
            state_name,
            state_description.text,
            next_state
        );
    };
}

// launch app
var states = new DialogueStateCreator();
var im = new InteractionMachine(api, states);
im.attach();