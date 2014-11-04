var Q = require('q');
var _ = require('lodash');
var vumigo = require('vumigo_v02');

var App = vumigo.App;
var EndState = vumigo.states.EndState;
var FreeText = vumigo.states.FreeText;
var Choice = vumigo.states.Choice;
var ChoiceState = vumigo.states.ChoiceState;
var InteractionMachine = vumigo.InteractionMachine;


var DialogueApp = App.extend(function(self) {
    App.call(self, 'states:start');

    self.poll_defaults = {
        states: [],
        accept_labels: true,
        start_state: {uuid: null},
        poll_metadata: {repeatable: false}
    };

    self.init = function() {
        return Q
            .all([self.get_poll(), self.im.contacts.for_user()])
            .spread(function(poll, contact) {
                self.poll = poll;
                self.contact = contact;
                self.poll.states.forEach(self.add_state);
            });
    };

    self.get_poll = function() {
        return self
            .im.sandbox_config.get('poll', {json: false})
            .then(function(poll) {
                return _.defaults(poll, self.poll_defaults);
            });
    };

    self.add_state = function(desc) {
        var type = self.types[desc.type];

        if (!type) {
            throw new Error(
                "Unknown dialogue state type: '" + desc.type + "'");
        }

        return self.states.add(desc.uuid, function() {
            return type(desc);
        });
    };

    self.next = function(endpoint) {
        var connection = _.find(self.poll.connections, {
            source: {uuid: endpoint.uuid}
        });

        if (!connection) { return null; }

        var state = _.find(self.poll.states, {
            entry_endpoint: {uuid: connection.target.uuid}
        });

        return state
            ? state.uuid
            : null;
    };

    self.types = {};

    self.types.choice = function(desc) {
        var endpoints = desc.choice_endpoints;

        return new ChoiceState(desc.uuid, {
            accept_labels: self.poll.accept_labels,

            question: desc.text,

            choices: endpoints.map(function(endpoint) {
                return new Choice(endpoint.value, endpoint.label);
            }),

            next: function(choice) {
                var endpoint = _.find(endpoints, {value: choice.value});

                if (!endpoint) { return; }
                self.contact.extra[desc.store_as] = endpoint.value;

                return self
                    .im.contacts.save(self.contact)
                    .thenResolve(self.next(endpoint));
            }
        });
    };

    self.types.freetext = function(desc) {
        return new FreeText(desc.uuid, {
            question: desc.text,

            next: function(content) {
                self.contact.extra[desc.store_as] = content;

                return self
                    .im.contacts.save(self.contact)
                    .thenResolve(self.next(desc.exit_endpoint));
            }
        });
    };

    self.types.end = function(desc) {
        return new EndState(desc.uuid, {
            text: desc.text,

            next: self.poll.poll_metadata.repeatable
                ? 'states:start'
                : null
        });
    };

    self.types.group = function(desc) {
        if (desc.group) {
          self.contact.groups.push(desc.group.key);
        }

        return self.im.contacts.save(self.contact).then(function() {
            return self.states.create(self.next(desc.exit_endpoint));
        });
    };

    self.types.send = function(desc) {
        return self
            .im.outbound.send({
                to: self.contact,
                content: desc.text,
                endpoint: desc.channel_type
            })
            .then(function() {
                return self.states.create(self.next(desc.exit_endpoint));
            });
    };

    self.states.add('states:start', function() {
        return self.states.create(self.poll.start_state.uuid);
    });
});


if (typeof api != 'undefined') {
    new InteractionMachine(api, new DialogueApp());
}


this.DialogueApp = DialogueApp;
