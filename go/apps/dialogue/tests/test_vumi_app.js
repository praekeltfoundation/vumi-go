var assert = require("assert");
var vumigo = require("vumigo_v01");
var app = require("../vumi_app");
var dummy_polls = require("./dummy_polls");

function poll_tester(poll) {
    return new vumigo.test_utils.ImTester(app.api, {
        async: true,
        custom_setup: function (api) {
            api.config_store.poll = JSON.stringify(poll);
        }
    });
}

describe("choice states", function() {
    var tester;

    beforeEach(function () {
        tester = poll_tester(dummy_polls.simple_poll);
    });

    it("should display", function(done) {
        var p = tester.check_state({
            user: {current_state: "choice-1"},
            content: null,
            next_state: "choice-1",
            response: (
                "^What is your favourite colour\\?[^]" +
                "1. Red[^]" +
                "2. Blue"
            )
        });
        p.then(done, done);
    });

    it("should respond to valid input", function(done) {
        var p = tester.check_state({
            user: {current_state: "choice-1"},
            content: "2",
            next_state: "end-1",
            response: (
                "^Thank you for taking our survey$"
            ),
            continue_session: false
        });
        p.then(done, done);
    });

    it("should respond to invalid input", function(done) {
        var p = tester.check_state({
            user: {current_state: "choice-1"},
            content: "3",
            next_state: "choice-1",
            response: (
                "^What is your favourite colour\\?[^]" +
                "1. Red[^]" +
                "2. Blue"
            )
        });
        p.then(done, done);
    });

});

describe("freetext states", function() {
    var tester;

    beforeEach(function () {
        tester = poll_tester(dummy_polls.simple_poll);
    });

    it("should display", function(done) {
        var p = tester.check_state({
            user: {current_state: "freetext-1"},
            content: null,
            next_state: "freetext-1",
            response: (
                "^What is your name\\?$"
            )
        });
        p.then(done, done);
    });

    it("should respond to input", function(done) {
        var p = tester.check_state({
            user: {current_state: "freetext-1"},
            content: "Foo",
            next_state: "end-1",
            response: (
                "^Thank you for taking our survey$"
            ),
            continue_session: false
        });
        p.then(done, done);
    });

});

describe("end states", function() {
    var tester;

    beforeEach(function () {
        tester = poll_tester(dummy_polls.simple_poll);
    });

    it("should display", function(done) {
        var p = tester.check_state({
            user: {current_state: "end-1"},
            content: null,
            next_state: "end-1",
            response: (
                "^Thank you for taking our survey$"
            ),
            continue_session: false
        });
        p.then(done, done);
    });
});

describe("states of unknown type", function() {
    var tester;

    beforeEach(function () {
        tester = poll_tester(dummy_polls.simple_poll);
    });

    it("should display", function(done) {
        var p = tester.check_state({
            user: {current_state: "unknown-1"},
            content: null,
            next_state: "unknown-1",
            response: (
                "^An error occurred. Please try dial in again later\\.$"
            ),
            continue_session: false
        });
        p.then(done, done);
    });
});
