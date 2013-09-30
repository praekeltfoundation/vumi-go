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
        var p = new Promise();
        event.im.fetch_config_value("poll", false,
            function (poll) {
                self.poll = poll;

                self.start_state = poll.start_state
                  ? poll.start_state.uuid
                  : null;

                self.accept_labels = 'accept_labels' in poll
                  ? poll.accept_labels
                  : true;

                var states = poll.states || [];
                self.state_creators = {};
                states.forEach(function(state_description) {
                    self.add_creator(state_description.uuid,
                                     self.mk_state_creator(state_description));
                });
                p.callback();
            }
        );
        return p;
    };

    self.on_inbound_event = function(event) {
        var vumi_ev = event.data.event;
        event.im.log("Saw " + vumi_ev.event_type + " for message "
                     + vumi_ev.user_message_id + ".");
    };

    self.get_metadata = function(key) {
        var metadata = self.poll.poll_metadata || {};
        return metadata[key];
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
            function (s) {
                if (!s.entry_endpoint) return false;
                return (s.entry_endpoint.uuid == endpoint);
            });
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
        return self.get_state_by_entry_endpoint(connection.target.uuid);
    };

    self.mk_state_creator = function(state_description) {
        return function(state_name, im) {
            return self.generic_state_creator(state_name, im, state_description);
        };
    };

    self.generic_state_creator = function(state_name, im, state_description) {
        var creator = self[state_description.type + '_state_creator'];
        if (typeof creator === 'undefined') {
            creator = self.unknown_state_creator;
        }
        return creator(state_name, im, state_description);
    };

    self.store_answer = function(store_as, answer, im) {
        var msg = im.get_msg();

        var fields = {};
        fields[store_as] = answer;

        var p = im.api_request('contacts.get_or_create', {
            addr: msg.from_addr,
            delivery_class: msg.helper_metadata.delivery_class
        });

        p.add_callback(function(reply) {
            if (!reply.success) { return; }

            return im.api_request(
              'contacts.update_extras',
              {key: reply.contact.key, fields: fields});
        });
        return p;
    };

    self.choice_state_creator = function(state_name, im, state_description) {
        var choices = state_description.choice_endpoints.map(
            function (c) { return new Choice(c.value, c.label); });
        return new ChoiceState(
            state_name,
            function (choice, done) {
                var endpoint = state_description.choice_endpoints.filter(
                  function (c) { return (c.value == choice.value); })[0];

                if (!endpoint) { done(state_name); return; }

                var p = self.store_answer(
                    state_description.store_as,
                    endpoint.value,
                    im
                );
                p.add_callback(function() {
                    done(self.get_next_state(endpoint.uuid));
                });
            },
            state_description.text,
            choices,
            null,
            null,
            {accept_labels: self.accept_labels}
        );
    };

    self.freetext_state_creator = function(state_name, im, state_description) {
        return new FreeText(
            state_name,
            function (content, done) {
                var next = state_description.exit_endpoint.uuid;
                var p = self.store_answer(
                    state_description.store_as,
                    content,
                    im
                );
                p.add_callback(function() {
                    done(self.get_next_state(next));
                });
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

    self.unknown_state_creator = function(state_name, im, state_description) {
        return new EndState(
            state_name,
            "An error occurred. Please try dial in again later.",
            self.start_state
        );
    };
}

// launch app
var states = new DialogueStateCreator();
var im = new InteractionMachine(api, states);
im.attach();
