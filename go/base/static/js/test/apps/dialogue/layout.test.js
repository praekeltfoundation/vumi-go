describe("go.apps.dialogue.layout", function() {
  var dialogue = go.apps.dialogue;

  var DialogueStateLayout = dialogue.layout.DialogueStateLayout;

  var setUp = dialogue.testHelpers.setUp,
      tearDown = dialogue.testHelpers.tearDown,
      newDialogueDiagram = dialogue.testHelpers.newDialogueDiagram;

  describe(".DialogueStateLayout", function() {
    var states,
        layout;

    beforeEach(function() {
      setUp();
      var diagram = newDialogueDiagram();
      states = diagram.states.members.get('states');
      layout = states.layout;
      diagram.render();
    });

    afterEach(function() {
      tearDown();
    });

    describe("when a state is dragged", function() {
      it("should repaint", function() {
        var repainted = false;
        var state2 = states.get('state2');
        layout.on('repaint', function() { repainted = true; });

        assert(!repainted);

        state2.$('.titlebar')
          .simulate('mousedown')
          .simulate('drag', {
            dx: 4,
            dy: 5
           });

        assert(repainted);
      });

      it("should update the relevant state's layout", function() {
        var state2 = states.get('state2');

        state2.model.get('layout').set({
          x: 0,
          y: 0
        });

        assert.notDeepEqual(state2.model.get('layout').coords(), {
          x: state2.$el.position().left,
          y: state2.$el.position().top
        });

        state2.$('.titlebar')
          .simulate('mousedown')
          .simulate('drag', {
            dx: 1,
            dy: 1
           });

        assert.deepEqual(state2.model.get('layout').coords(), {
          x: state2.$el.position().left,
          y: state2.$el.position().top
        });
      });
    });

    describe(".render", function() {
      it("should initialise states without a layout )using the grid", function() {
        var layout = new DialogueStateLayout({
          states: states,
          numCols: 2
        });

        var state2 = states.get('state2');
        var state3 = states.get('state3');
        var state4 = states.get('state4');
        state2.model.unset('layout');
        state3.model.unset('layout');
        state4.model.unset('layout');

        state2.$el
          .css('margin', 20)
          .width(202)
          .height(200);

        state3.$el
          .css('margin', 30)
          .width(303)
          .height(300);

        state4.$el
          .css('margin', 40)
          .height(404)
          .height(400);

        layout.render();

        assert.deepEqual(state2.model.get('layout').coords(), {
          x: 20,
          y: 20
        });

        assert.deepEqual(state3.model.get('layout').coords(), {
          x: 272,
          y: 30
        });

        assert.deepEqual(state4.model.get('layout').coords(), {
          x: 40,
          y: 280
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
          .width(202)
          .height(200);

        state3.$el
          .css('margin', 30)
          .width(303)
          .height(300);

        state4.$el
          .css('margin', 40)
          .width(404)
          .height(400);

        layout.render();

        assert.deepEqual(state2.$el.offset(), layout.offsetOf({
          x: 20,
          y: 20
        }));

        assert.deepEqual(state3.$el.offset(), layout.offsetOf({
          x: 272,
          y: 30
        }));

        assert.deepEqual(state4.$el.offset(), layout.offsetOf({
          x: 40,
          y: 280
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

    describe(".repaint", function() {
      it("should repaint the relevant jsPlumb connections", function() {
        sinon.spy(jsPlumb, 'repaintEverything');

        var layout = new DialogueStateLayout({states: states});
        assert(!jsPlumb.repaintEverything.called);
        layout.repaint();
        assert(jsPlumb.repaintEverything.called);

        jsPlumb.repaintEverything.restore();
      });
    });
  });
});
