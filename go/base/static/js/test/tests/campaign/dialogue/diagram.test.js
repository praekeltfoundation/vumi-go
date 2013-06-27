describe("go.campaign.dialogue.diagram", function() {
  var testHelpers = go.testHelpers,
      oneElExists = testHelpers.oneElExists,
      noElExists = testHelpers.noElExists;

  var dialogue = go.campaign.dialogue,
      states = go.campaign.dialogue.states;

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

  describe(".DialogueDiagramView", function() {
    describe(".render", function() {
      it("should render its states", function() {
        assert(noElExists(diagram.$('.state')));
        diagram.render();

        assert(oneElExists(diagram.$('.state[data-uuid="state1"]')));
        assert(oneElExists(diagram.$('.state[data-uuid="state2"]')));
        assert(oneElExists(diagram.$('.state[data-uuid="state3"]')));
        assert(oneElExists(diagram.$('.state[data-uuid="state4"]')));
      });

      it("should render its connections", function() {
        var e1_e3 = diagram.connections.get('endpoint1-endpoint3');

        assert(_.isEmpty(jsPlumb.getConnections()));
        diagram.render();

        assert.deepEqual(
          jsPlumb.getConnections(),
          [e1_e3.plumbConnection]
        );
      });
    });
  });
});
