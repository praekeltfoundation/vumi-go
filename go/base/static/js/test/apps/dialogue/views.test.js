describe("go.apps.dialogue.views", function() {
  var setUp = go.apps.dialogue.testHelpers.setUp,
      tearDown = go.apps.dialogue.testHelpers.tearDown,
      modelData = go.apps.dialogue.testHelpers.modelData;

  var testHelpers = go.testHelpers,
      oneElExists = testHelpers.oneElExists,
      noElExists = testHelpers.noElExists,
      response = testHelpers.rpc.response,
      errorResponse = testHelpers.rpc.errorResponse,
      assertRequest = testHelpers.rpc.assertRequest;

  describe(".DialogueView", function() {
    var DialogueView = go.apps.dialogue.views.DialogueView,
        DialogueModel = go.apps.dialogue.models.DialogueModel;

    var view,
        server;

    beforeEach(function() {
      setUp();

      server = sinon.fakeServer.create();

      view = new DialogueView({
        el: $('.dialogue'),
        model: new DialogueModel(modelData()),
        sessionId: '123'
      });

      view.save.notifier.animate = false;
      view.render();
    });

    afterEach(function() {
      tearDown();
      view.remove();
      server.restore();
    });

    describe("when the '#save' is clicked", function() {
      it("should issue a save api call with the dialogue changes",
      function(done) {
        server.respondWith(function(req) {
          assertRequest(
            req,
            '/api/v1/go/api',
            'conversation.dialogue.save_poll',
            ['campaign-1', 'conversation-1', {poll: view.model.toJSON()}]);

          done();
        });

        // modify the diagram
        view.diagram.connections.remove('endpoint1-endpoint3');
        assert.notDeepEqual(view.model.toJSON(), modelData());

        view.$('#save').click();
        server.respond();
      });

      describe("when the save action was not successful", function() {
        it("should notify the user", function() {
          server.respondWith(errorResponse('Aaah!'));

          view.$('#save').click();
          server.respond();

          assert.include(view.save.notifier.$el.text(), "Save failed.");
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

        it("should notify the user", function() {
          server.respondWith(response());

          view.$('#save').click();
          server.respond();

          assert.include(view.save.notifier.$el.text(), "Save successful.");
        });

        it("should redirect the user to the conversation show page",
        function() {
          server.respondWith('{}');

          view.$('#save').click();
          server.respond();

          assert.equal(location, 'conversation:show:conversation-1');
        });
      });
    });

    describe("when '#repeatable' is changed", function() {
      it("should change the model metadata's 'repeatable' attribute",
      function() {
        assert(!view.model.get('poll_metadata').get('repeatable'));
        view.$('#repeatable').prop('checked', true).change();
        assert(view.model.get('poll_metadata').get('repeatable'));

        view.$('#repeatable').prop('checked', false).change();
        assert(!view.model.get('poll_metadata').get('repeatable'));
      });
    });

    describe("when '#delivery-class' is changed", function() {
      it("should change the model metadata's 'delivery_class' attribute",
      function() {
        var metadata = view.model.get('poll_metadata');
        assert.equal(metadata.get('delivery_class'), 'ussd');
        view.$('#delivery-class').val('twitter').change();
        assert.equal(metadata.get('delivery_class'), 'twitter');
      });
    });
  });
});
