require('mocha-as-promised')();
var vumigo = require('vumigo_v02');
var app = require('../vumi_app');
var DialogueApp = app.DialogueApp;
var AppTester = vumigo.AppTester;

describe.only("app", function() {
    describe("DialogueApp", function() {
        var tester;
        
        beforeEach(function() {
            tester = new AppTester(new DialogueApp());

            tester.setup.config.app({
                name: 'dialogue_app'
            });
        });

        describe("when the user enters a choice state", function() {
            it("should display the state's question");
            it("should respond to valid input");
            it("should respond to invalid input");
            it("should store the user's answer");
            it("should support accepting label and number based answers");
        });

        describe("when the user enters a freetext state", function() {
            it("should display the state's question");
            it("should respond to input");
            it("should store the user's answer");
        });

        describe("when the user enters an end state", function() {
            it("should display the state's text");
            it("should put the user on the start state next session");
        });
    });
});
