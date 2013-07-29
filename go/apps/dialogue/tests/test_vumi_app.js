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

    it("should respond to valid input", function(done) {
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

    it.skip("should respond to invalid input", function(done) {
    });

});

describe("freetext states", function() {
    var tester;

    beforeEach(function () {
        tester = poll_tester(dummy_polls.simple_poll);
    });

    it.skip("should respond to valid input", function(done) {
    });

});

describe("end states", function() {
    var tester;

    beforeEach(function () {
        tester = poll_tester(dummy_polls.simple_poll);
    });

    it.skip("should respond to valid input", function(done) {
    });
});

describe("states of unknown type", function() {
    var tester;

    beforeEach(function () {
    });

    it.skip("should respond to valid input", function(done) {
    });
});
