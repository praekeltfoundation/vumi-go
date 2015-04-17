describe("go.apps.dialogue.layout", function() {
  var dialogue = go.apps.dialogue;

  var DialogueStateLayout = dialogue.layout.DialogueStateLayout;

  var setUp = dialogue.testHelpers.setUp,
      tearDown = dialogue.testHelpers.tearDown,
      newDialogueDiagram = dialogue.testHelpers.newDialogueDiagram;

  describe(".DialogueStateLayout", function() {
    var states;

    beforeEach(function() {
      setUp();
      var diagram = newDialogueDiagram();
      states = diagram.states.members.get('states');
      diagram.render();
    });

    afterEach(function() {
      tearDown();
    });

    describe(".render", function() {
      it("should initialise states without a layout using the grid", function() {
        var layout = new DialogueStateLayout({
          states: states,
          numCols: 2,
          colWidth: 220
        });

        var state2 = states.get('state2');
        var state3 = states.get('state3');
        var state4 = states.get('state4');
        state2.model.unset('layout');
        state3.model.unset('layout');
        state4.model.unset('layout');

        state2.$el
          .css('margin', 20)
          .height(200);

        state3.$el
          .css('margin', 30)
          .height(300);

        state4.$el
          .css('margin', 40)
          .height(400);

        layout.render();

        assert.deepEqual(state2.model.get('layout').coords(), {
          x: 20,
          y: 20
        });

        assert.deepEqual(state3.model.get('layout').coords(), {
          x: 250,
          y: 30
        });

        assert.deepEqual(state4.model.get('layout').coords(), {
          x: 40,
          y: 300
        });
      });

      it("should position states without a layout using the grid", function() {
        var layout = new DialogueStateLayout({
          states: states,
          numCols: 2,
          colWidth: 220
        });

        var state2 = states.get('state2');
        var state3 = states.get('state3');
        var state4 = states.get('state4');
        state2.model.unset('layout');
        state3.model.unset('layout');
        state4.model.unset('layout');

        state2.$el
          .css('margin', 20)
          .height(200);

        state3.$el
          .css('margin', 30)
          .height(300);

        state4.$el
          .css('margin', 40)
          .height(400);

        layout.render();

        assert.deepEqual(state2.$el.offset(), layout.offsetOf({
          x: 20,
          y: 20
        }));

        assert.deepEqual(state3.$el.offset(), layout.offsetOf({
          x: 250,
          y: 30
        }));

        assert.deepEqual(state4.$el.offset(), layout.offsetOf({
          x: 40,
          y: 300
        }));
      });

      it("should position states that have a layout", function() {
        var layout = new DialogueStateLayout({states: states});
        var state2 = states.get('state2');
        var state3 = states.get('state3');
        var state4 = states.get('state4');

        state2.model.get('layout').set({
          x: 20,
          y: 200
        });

        state3.model.get('layout').set({
          x: 30,
          y: 300
        });

        state4.model.get('layout').set({
          x: 40,
          y: 400
        });

        layout.render();

        assert.deepEqual(state2.$el.offset(), layout.offsetOf({
          x: 20,
          y: 200
        }));

        assert.deepEqual(state3.$el.offset(), layout.offsetOf({
          x: 30,
          y: 300
        }));

        assert.deepEqual(state4.$el.offset(), layout.offsetOf({
          x: 40,
          y: 400
        }));
      });
    });

    describe(".offsetOf", function() {
      it("should calculate the offset of the given coordinates", function() {
        var layout = new DialogueStateLayout({states: states});

        layout.$el.offset({
          left: 23,
          top: 32
        });

        assert.deepEqual(layout.offsetOf({
          x: -2,
          y: 1
        }), {
          left: 21,
          top: 33 
        });
      });
    });
  });
});
