describe("go.apps.dialogue.actions", function() {
  var dialogue = go.apps.dialogue;

  var setUp = dialogue.testHelpers.setUp,
      tearDown = dialogue.testHelpers.tearDown,
      newDialogueDiagram = dialogue.testHelpers.newDialogueDiagram,
      modelData = dialogue.testHelpers.modelData;

  var testHelpers = go.testHelpers,
      oneElExists = testHelpers.oneElExists,
      noElExists = testHelpers.noElExists,
      response = testHelpers.rpc.response,
      errorResponse = testHelpers.rpc.errorResponse,
      assertRequest = testHelpers.rpc.assertRequest;

  var diagram;

  beforeEach(function() {
    setUp();
    diagram = newDialogueDiagram();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".DialogueActionsView", function() {
    var DialogueActionsView = dialogue.actions.DialogueActionsView;

    var actions,
        server;

    beforeEach(function() {
      server = sinon.fakeServer.create();

      var $el = $('<div>')
        .append($('<button>').attr('data-action', 'new-state'))
        .append($('<button>').attr('data-action', 'save'));

      actions = new DialogueActionsView({
        el: $el,
        diagram: diagram,
        sessionId: '123'
      });

      diagram.render();
      bootbox.animate(false);
    });

    afterEach(function() {
      actions.remove();
      server.restore();

      $('.bootbox')
      .modal('hide')
      .remove();
    });

    describe("when the save button is clicked", function() {
      it("should issue a save api call with the dialogue changes",
      function(done) {
        server.respondWith(function(req) {
          assertRequest(
            req,
            '/api/v1/go/api',
            'conversation.dialogue.save_poll',
            ['campaign-1', 'conversation-1', diagram.model.toJSON()]);

          done();
        });

        // modify the diagram
        diagram.connections.remove('endpoint1-endpoint3');
        assert.notDeepEqual(diagram.model.toJSON(), modelData);

        actions.$('[data-action=save]').click();
        server.respond();
      });

      describe("when the save action was not successful", function() {
        it("should notify the user", function() {
          server.respondWith(errorResponse('Aaah!'));

          // modify the diagram
          assert(noElExists('.modal'));

          actions.$('[data-action=save]').click();
          server.respond();

          assert(oneElExists('.modal'));
          assert.include(
            $('.modal').text(),
            "Something bad happened, changes couldn't be save");
        });
      });

      describe("if the save action was successful", function() {
        var location;

        beforeEach(function() {
          sinon.stub(go.utils, 'redirect', function(url) { location = url; });
        });

        afterEach(function() {
          go.utils.redirect.restore();
        });

        it("should send the user to the conversation show page", function() {
          server.respondWith(response());

          actions.$('[data-action=save]').click();
          server.respond();

          assert.equal(location, '/conversations/conversation-1/');
        });
      });
    });

    describe("when the 'new state' button is clicked", function() {
      var i;

      beforeEach(function() {
        i = 0;
        diagram.render();
        sinon.stub(uuid, 'v4', function() { return i++ || 'new-state'; });
      });

      it("should add a new state to the diagram", function() {
        assert(noElExists('[data-uuid=new-state]'));
        actions.$('[data-action=new-state]').click();
        assert(oneElExists('[data-uuid=new-state]'));
      });
    });
  });
});
