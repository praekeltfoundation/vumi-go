describe("go.apps.dialogue.entry", function() {
  var dialogue = go.apps.dialogue;

  var setUp = dialogue.testHelpers.setUp,
      tearDown = dialogue.testHelpers.tearDown,
      newDialogueDiagram = dialogue.testHelpers.newDialogueDiagram;

  var diagram,
      entryPoint;

  beforeEach(function() {
    setUp();
    diagram = newDialogueDiagram();
    entryPoint = diagram.entryPoint;
    diagram.render();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".DialogueEntryPointView", function() {
    describe("when its target is destroyed", function() {
      it("should detach", function() {
        var detached;
        diagram.render();

        detached = false;
        entryPoint.on('detach', function() { detached = true; });
        entryPoint.target.destroy();
        assert(detached);
      });
    });

    describe("when a new connection is made", function() {
      it("should set its new target", function() {
        var endpoint = diagram.endpoints.get('endpoint2');
        var target;

        entryPoint.on('set:target', function(newTarget) {
          target = newTarget;
        });

        jsPlumb.connect({
          source: entryPoint.$endpoint,
          target: endpoint.$el
        });

        assert.strictEqual(target, endpoint);
      });

      it("should set its new connection", function() {
        var conn;

        conn = jsPlumb.connect({
          source: entryPoint.$endpoint,
          target: diagram.endpoints.get('endpoint2').$el
        });

        assert.strictEqual(entryPoint.plumbConnection, conn);
      });
    });

    describe(".connect", function() {
      it("should create a new plumb connection", function() {
        var endpoint = diagram.endpoints.get('endpoint2');

        assert(entryPoint.$endpoint.is(entryPoint.plumbConnection.source));
        assert(!endpoint.$el.is(entryPoint.plumbConnection.target));
        entryPoint.connect(endpoint);
        assert(entryPoint.$endpoint.is(entryPoint.plumbConnection.source));
        assert(endpoint.$el.is(entryPoint.plumbConnection.target));
      });

      it("should trigger an event", function() {
        var target;
        var endpoint = diagram.endpoints.get('endpoint2');

        entryPoint.on('connect', function(newTarget) {
          target = newTarget;
        });

        entryPoint.connect(endpoint);
        assert(target, endpoint);
      });
    });

    describe(".detach", function() {
      it("should detach its plumb connection", function() {
        var detached = false;

        jsPlumb.bind('connectionDetached', function() {
          detached = true;
        });

        entryPoint.detach({fireEvent: true});
        assert(detached);
      });

      it("should unset its target", function() {
        var target = entryPoint.target;
        var unsetTarget;

        entryPoint.on('unset:target', function(target) {
          unsetTarget = target;
        });

        entryPoint.detach();
        assert.strictEqual(unsetTarget, target);
      });

      it("should trigger an event", function() {
        var detached = false;

        entryPoint.on('detach', function() {
          detached = true;
        });

        entryPoint.detach();
        assert(detached);
      });
    });

    describe(".setTarget", function() {
      it("should unset its current target", function() {
        var target = entryPoint.target;
        var unsetTarget;

        entryPoint.on('unset:target', function(target) {
          unsetTarget = target;
        });

        entryPoint.setTarget(diagram.endpoints.get('endpoint2'));
        assert.strictEqual(unsetTarget, target);
      });

      it("should set the new target", function() {
        var endpoint = diagram.endpoints.get('endpoint2');
        assert.notStrictEqual(entryPoint.target, endpoint);
        entryPoint.setTarget(endpoint);
        assert.strictEqual(entryPoint.target, endpoint);
      });

      it("should set the diagram model's start state", function() {
        var endpoint = diagram.endpoints.get('endpoint2');
        assert.notStrictEqual(entryPoint.target.model, endpoint.model);
        entryPoint.setTarget(endpoint);
        assert.strictEqual(entryPoint.target.model, endpoint.model);
      });

      it("should trigger an event", function() {
        var endpoint = diagram.endpoints.get('endpoint2');
        var setTarget;

        entryPoint.on('set:target', function(target) {
          setTarget = target;
        });

        entryPoint.setTarget(endpoint);
        assert.strictEqual(setTarget, endpoint);
      });
    });

    describe(".unsetTarget", function() {
      it("should unset the diagram model's start state", function() {
        assert(diagram.model.has('start_state'));
        entryPoint.unsetTarget();
        assert(!diagram.model.has('start_state'));
      });

      it("should trigger an event", function() {
        var target = entryPoint.target;
        var unsetTarget;

        entryPoint.on('unset:target', function(target) {
          unsetTarget = target;
        });

        entryPoint.unsetTarget();
        assert.strictEqual(unsetTarget, target);
      });
    });

    describe(".getTarget", function() {
      it("should get current start state's entry endpoint", function() {
        var endpoint = diagram.endpoints.get('endpoint2');
        diagram.model.set('start_state', endpoint.state.model);
        assert.strictEqual(entryPoint.getTarget().id, endpoint.id);
      });
    });

    describe(".render", function() {
      it("should render its text", function() {
        entryPoint.$el.empty();
        entryPoint.render();
        assert.equal(entryPoint.$el.text(), 'Start');
      });

      it("should render its endpoint", function() {
        entryPoint.$el.empty();
        entryPoint.render();
        assert.equal(entryPoint.$('.endpoint').length, 1);
      });

      it("should connect if it is not yet connected", function() {
        var endpoint = diagram.endpoints.get('endpoint2');
        var connected = false;

        entryPoint.detach();
        diagram.model.set('start_state', endpoint.state.model);

        entryPoint.on('connect', function() {
          connected = true;
        });

        entryPoint.render();
        assert(connected);
      });
    });
  });
});
