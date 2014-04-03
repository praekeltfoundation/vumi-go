var Q = require('q');
var _ = require('lodash');
var vumigo = require('vumigo_v02');

var App = vumigo.App;
var State = vumigo.states.State;
var InteractionMachine = vumigo.InteractionMachine;


var DialogueApp = App.extend(function(self) {
    App.call(self, 'states:start');

    self.poll_defaults = {
        states: [],
        repeatable: false,
        accept_labels: true,
        start_state: {uuid: null}
    };

    self.events = {
        'im im:shutdown': function() {
            return self.contacts.save(self.contact);
        }
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
            .im.sandbox_config.get('poll', {json: true})
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

        return self.states.add(type(desc));
    };

    self.types = {};

    self.types.choice = function(desc) {
        return new State(desc.uuid);
    };

    self.types.freetext = function(desc) {
        return new State(desc.uuid);
    };

    self.types.end = function(desc) {
        return new State(desc.uuid);
    };

    self.states.add('states:start', function() {
        return self.states.create(self.poll.start_state.uuid);
    });
});


if (typeof api != 'undefined') {
    new InteractionMachine(api, new DialogueApp());
}


this.DialogueApp = DialogueApp;
