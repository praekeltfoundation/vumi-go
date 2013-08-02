describe("go.apps.dialogue.connections", function() {
  var testHelpers = go.testHelpers,
      oneElExists = testHelpers.oneElExists,
      noElExists = testHelpers.noElExists;

  var dialogue = go.apps.dialogue,
      states = go.apps.dialogue.states;

  var setUp = dialogue.testHelpers.setUp,
      tearDown = dialogue.testHelpers.tearDown,
      newDialogueDiagram = dialogue.testHelpers.newDialogueDiagram;

  var diagram;

  beforeEach(function() {
    setUp();
    diagram = newDialogueDiagram();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".DialogueConnectionCollection", function() {
    var connections;

    beforeEach(function() {
      connections = diagram.connections.members.get('connections');
    });

    describe(".accepts", function() {
      it("should return false for connections on the same state", function() {
        assert(!connections.accepts(
          diagram.states.at(0).endpoints.at(0),
          diagram.states.at(0).endpoints.at(1)));
      });
    });
  });
});
