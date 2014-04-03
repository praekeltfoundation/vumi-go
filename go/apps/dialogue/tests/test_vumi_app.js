require('mocha-as-promised')();
var assert = require('assert');

var _ = require('lodash');
var vumigo = require('vumigo_v02');
var AppTester = vumigo.AppTester;

var app = require('../vumi_app');
var DialogueApp = app.DialogueApp;
var dummy_polls = require('./dummy_polls');

describe.only("app", function() {
    describe("DialogueApp", function() {
        var tester;
        
        beforeEach(function() {
            tester = new AppTester(new DialogueApp())
                .setup.config.app({name: 'dialogue_app'})
                .setup.config({poll: dummy_polls.simple_poll});
        });

        it("should throw an error if an unknown state type is encountered",
        function() {
            return tester
                .setup.config({
                    poll: _.extend({}, dummy_polls.simple_poll, {
                        states: [{type: 'unknown'}]
                    })
                })
                .run()
                .catch(function(e) {
                    assert(e instanceof Error);
                    assert.equal(
                        e.message,
                        "Unknown dialogue state type: 'unknown'");
                });
        });

        describe("when the user enters a choice state", function() {
            it("should display the state's question");
            it("should move the user to the next state on valid input");
            it("should stay on the same state on invalid input");
            it("should store the user's answer");
            it("should only accept number based answers if asked");
            it("should accept label and number based answers if asked");
        });

        describe("when the user enters a freetext state", function() {
            it("should display the state's question");
            it("should move the user to the next state on valid input");
            it("should store the user's answer");
        });

        describe("when the user enters an end state", function() {
            it("should display the state's text");
            it("should move to the start state next session if asked");
            it("should not move to the start state next session if asked");
        });
    });
});
