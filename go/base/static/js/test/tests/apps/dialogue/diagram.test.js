describe("go.apps.dialogue.diagram", function() {
  var testHelpers = go.testHelpers,
      oneElExists = testHelpers.oneElExists,
      noElExists = testHelpers.noElExists;

  var plumbing = go.components.plumbing,
      noConnections = plumbing.testHelpers.noConnections;

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

  describe(".DialogueDiagramView", function() {
    describe("when an unsupported connection was created", function() {
      beforeEach(function() {
        diagram.render();
      });

      it("should detach the jsPlumb connection", function(done) {
        var e1 = diagram.endpoints.get('endpoint1'),
            e2 = diagram.endpoints.get('endpoint2');

        diagram.connections.on('error:unsupported', function() {
          assert(noConnections(e1, e2));
          done();
        });

        jsPlumb.connect({source: e1.$el, target: e2.$el});
      });
    });

    describe("when its states are reordered", function() {
      var states;

      beforeEach(function() {
        states = diagram.dialogueStates;
        diagram.render();
      });

      it("should change its model's accordingly start state", function() {
        assert.equal(
          diagram.model.get('start_state'),
          states.get('state1').model);

        assert.deepEqual(
          states.keys(),
          ['state1','state2','state3','state4']);

        $('[data-uuid="state3"] .titlebar')
          .simulate('mousedown')
          .simulate('drag', {dx: -700});

        assert.deepEqual(
          states.keys(),
          ['state3','state1','state2','state4']);

        assert.equal(
          diagram.model.get('start_state'),
          states.get('state3').model);
      });
    });

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
