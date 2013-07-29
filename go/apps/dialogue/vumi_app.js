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

    self.on_config_read = function (event) {
        var poll = event.config.poll || {};
        var states = poll.states || [];
        states.forEach(function(state_description) {
            self.add_creator(state.uuid,
                             self.mk_state_creator(state_description));
        });
    };

    self.mk_state_creator = function (state_description) {
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

    self.choice_state_creator(state_name, im, state_description) {
        return new ChoiceState(
            state_name,
            function (choice) {
                return next_state;
            },
            state_description.text,
            choices
        );
    };

    self.freetext_state_creator(state_name, im, state_description) {
        return new FreeText(
            state_name,
            next_state,
            state_description.text
        );
    };

    self.end_state_creator(state_name, im, state_description) {
        return new EndState(
            state_name,
            state_description.text,
            next_state
        );
    };

    // TOOD: figure out
    StateCreator.call(self, 'first_state');
}

// launch app
var states = new DialogueStateCreator();
var im = new InteractionMachine(api, states);
im.attach();