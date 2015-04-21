describe("go.apps.dialogue.layout", function() {
  var dialogue = go.apps.dialogue;

  var DialogueStateLayout = dialogue.layout.DialogueStateLayout;

  var setUp = dialogue.testHelpers.setUp,
      tearDown = dialogue.testHelpers.tearDown,
      newDialogueDiagram = dialogue.testHelpers.newDialogueDiagram;

  describe(".DialogueStateLayout", function() {
    var diagram,
        states,
        layout;

    beforeEach(function() {
      setUp();
      diagram = newDialogueDiagram();
      states = diagram.states.members.get('states');
      layout = states.layout;
      diagram.render();
    });

    afterEach(function() {
      tearDown();
    });

    it("should set up dragging for states", function() {
      var state2 = states.get('state2');
      var oldPosition = state2.$el.position();

      state2.$('.titlebar')
        .simulate('mousedown')
        .simulate('drag', {
          dx: 4,
          dy: 5
         });

      assert.notDeepEqual(state2.$el.position(), oldPosition);
    });

    describe("when the layout is double-clicked", function() {
      it("should create a new state at the mouse position", function() {
        var offset = layout.offsetOf({
          x: 21,
          y: 23
        }) ;

        assert.strictEqual(states.size(), 5);

        layout.$el.trigger($.Event('dblclick', {
          pageX: offset.left,
          pageY: offset.top
        }));

        assert.strictEqual(states.size(), 6);

        var state = states.last();
        assert.deepEqual(state.model.get('layout').coords(), {
          x: 21,
          y: 23
        });
        assert.deepEqual(state.$el.offset(), layout.offsetOf({
          x: 21,
          y: 23
        }));
      });
    });

    describe("when a new state is added", function() {
      it("should set up dragging for the state", function() {
        var state = states.add();
        var oldPosition = state.$el.position();

        state.$('.titlebar')
          .simulate('mousedown')
          .simulate('drag', {
            dx: 4,
            dy: 5
           });

        assert.notDeepEqual(state.$el.position(), oldPosition);
      });
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
        var state = states.get('state2');

        state.model.get('layout').set({
          x: 0,
          y: 0
        });

        assert.notDeepEqual(
          state.model.get('layout').coords(),
          layout.coordsOf(state));

        state.$('.titlebar')
          .simulate('mousedown')
          .simulate('drag', {
            dx: 1,
            dy: 1
          });

        assert.deepEqual(
          state.model.get('layout').coords(),
          layout.coordsOf(state));
      });

      it("should resize its height to fit the state's new position", function() {
        var state2 = states.get('state2');
        diagram.model.get('states').set([state2.model]);
        layout.dragMargin = go.utils.functor(10);

        layout.$el
          .css('min-height', 10)
          .height(10);

        state2.$el
          .css('padding', 0)
          .css('margin', 0)
          .height(80);

        state2.model
          .get('layout')
          .set('y', 0);

        layout.render();

        assert.strictEqual(layout.$el.height(), 80 + 10);

        state2.$('.titlebar')
          .simulate('mousedown')
          .simulate('drag', {dy: 1});

        assert.strictEqual(
          layout.$el.height(),
          state2.$el.position().top + 80 + 10);
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
      
      it("should resize its height to fit all its states", function() {
        var state2 = states.get('state2');
        var state3 = states.get('state3');
        layout.dragMargin = go.utils.functor(10);

        diagram.model.get('states').set([
          state2.model,
          state3.model
        ]);

        layout.$el
          .css('min-height', 10)
          .height(200);

        state2.$el
          .css('padding', 0)
          .css('margin', 20)
          .height(200);

        state3.$el
          .css('padding', 0)
          .css('margin', 30)
          .height(300);

        state2.model
          .get('layout')
          .set('y', 40);

        state3.model
          .get('layout')
          .set('y', 60);

        layout.render();

        assert.strictEqual(layout.$el.height(), 30 + 300 + 60 + 10);
      });
    });

    describe(".offsetOf", function() {
      it("should calculate the offset of the given coordinates", function() {
        layout.$el.offset({
          left: 23,
          top: 32
        });

        assert.deepEqual(layout.offsetOf({
          x: -2,
          y: 1
        }), {
          left: 23 - 2,
          top: 32 + 1 
        });
      });
    });

    describe(".coordsOf", function() {
      it("should calculate coords of the given state", function() {
        var state = states.get('state2');

        layout.$el.offset({
          left: 23,
          top: 32
        });

        state.$el.offset({
          left: 200,
          top: 300
        });

        assert.deepEqual(layout.coordsOf(state), {
          x: 200 - 23,
          y: 300 - 32 
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
