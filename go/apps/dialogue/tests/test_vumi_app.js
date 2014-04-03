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
        var poll;
        var tester;
        
        beforeEach(function() {
            poll = _.cloneDeep(dummy_polls.simple_poll);

            tester = new AppTester(new DialogueApp())
                .setup.config.app({name: 'dialogue_app'})
                .setup.config({poll: poll})
                .setup.user.addr('+27123');
        });

        it("should throw an error if an unknown state type is encountered",
        function() {
            return tester
                .setup.config({
                    poll: _.extend(poll, {
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

        it("should stay on the same state if a state has no next state",
        function() {
            return tester
                .setup.config({
                    poll: _.extend(poll, {connections: []})
                })
                .setup.user.state('choice-1')
                .input('1')
                .check.user.state('choice-1')
                .run();
        });

        describe("when the user enters a choice state", function() {
            it("should display the state's question", function() {
                return tester
                    .start()
                    .check.user.state('choice-1')
                    .check.reply([
                        "What is your favourite colour?",
                        "1. Red",
                        "2. Blue"
                    ].join('\n'))
                    .run();
            });

            it("should move the user to the next state on valid input",
            function() {
                return tester
                    .setup.user.state('choice-1')
                    .input('1')
                    .check.user.state('freetext-1')
                    .run();
            });

            it("should stay on the same state on invalid input", function() {
                return tester
                    .setup.user.state('choice-1')
                    .input('23')
                    .check.user.state('choice-1')
                    .run();
            });

            it("should store the user's answer", function() {
                return tester
                    .setup.user.state('choice-1')
                    .input('1')
                    .check(function(api) {
                        var contact = _.find(api.contacts.store, {
                            msisdn: '+27123'
                        });

                        assert.equal(contact.extra['message-1'], 'value-1');
                    })
                    .run();
            });

            it("should only accept number based answers if asked", function() {
                return tester
                    .setup.config({
                        poll: _.extend(poll, {accept_labels: false})
                    })
                    .setup.user.state('choice-1')
                    .input('Red')
                    .check.user.state('choice-1')
                    .run();
            });

            it("should accept label and number based answers if asked",
            function() {
                return tester
                    .setup.config({
                        poll: _.extend(poll, {accept_labels: true})
                    })
                    .setup.user.state('choice-1')
                    .input('Red')
                    .check.user.state('freetext-1')
                    .run();
            });
        });

        describe("when the user enters a freetext state", function() {
            it("should display the state's question", function() {
                return tester
                    .setup.user.state('choice-1')
                    .input('1')
                    .check.user.state('freetext-1')
                    .check.reply('What is your name?')
                    .run();
            });

            it("should move the user to the next state on valid input",
            function() {
                return tester
                    .setup.user.state('freetext-1')
                    .input('foo')
                    .check.user.state('end-1')
                    .run();
            });

            it("should store the user's answer", function() {
                return tester
                    .setup.user.state('freetext-1')
                    .input('foo')
                    .check(function(api) {
                        var contact = _.find(api.contacts.store, {
                            msisdn: '+27123'
                        });

                        assert.equal(contact.extra['message-2'], 'foo');
                    })
                    .run();
            });
        });

        describe("when the user enters an end state", function() {
            it("should display the state's text", function() {
                return tester
                    .setup.user.state('choice-1')
                    .input('2')
                    .check.user.state('end-1')
                    .check.reply('Thank you for taking our survey')
                    .run();
            });

            it("should move to the start state next session if asked",
            function() {
                return tester
                    .setup.config({
                        poll: _.extend(poll, {repeatable: true})
                    })
                    .setup.user.state('end-1')
                    .start()
                    .check.user.state('choice-1')
                    .run();
            });

            it("should not move to the start state next session if asked",
            function() {
                return tester
                    .setup.config({
                        poll: _.extend(poll, {repeatable: false})
                    })
                    .setup.user.state('end-1')
                    .start()
                    .check.user.state('end-1')
                    .run();
            });
        });
    });
});
