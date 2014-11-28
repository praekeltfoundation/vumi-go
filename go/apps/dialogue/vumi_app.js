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
        poll_metadata: {repeatable: false},
        answers_delimiter: ';'
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

        self.states.remove(desc.uuid);
        return self.states.add(desc.uuid, function() {
            return type(desc);
        });
    };

    self.get_endpoint = function(channel_type) {
        var d = _.find(self.poll.channel_types, {name: channel_type});

        if (!d) {
            throw new Error(
                "No endpoint found for channel type '" + channel_type + "'");
        }

        return d.label;
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

    self.append_answer = function(answers, answer) {
        answers = answers || '';

        return answers.length
            ? [answers, answer].join(self.poll.answers_delimiter)
            : answer;
    };

    self.store_answer = function(key, value) {
        self.contact.extra[key] = value;

        var answers_key = key + '-answers';
        var answers = self.contact.extra[answers_key];
        self.contact.extra[answers_key] = self.append_answer(answers, value);
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
                self.store_answer(desc.store_as, endpoint.value);

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
                self.store_answer(desc.store_as, content);

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
                endpoint: self.get_endpoint(desc.channel_type)
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
