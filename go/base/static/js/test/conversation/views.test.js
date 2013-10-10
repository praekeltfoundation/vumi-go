describe("go.conversation.views", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists;
      oneElExists = testHelpers.oneElExists;

  describe("ConversationActionView", function() {
    var ConversationActionView = go.conversation.views.ConversationActionView;

    var action,
        server;

    beforeEach(function() {
      server = sinon.fakeServer.create();
      action = new ConversationActionView({
        el: $('<button>')
          .attr('data-url', '/conversation/action')
          .attr('data-action', 'action')
      });

      bootbox.setDefaults({animate: false});
    });

    afterEach(function() {
      server.restore();

      $('.bootbox')
        .hide()
        .remove();
    });

    describe(".invoke", function() {
      it("should display a confirmation modal", function() {
        assert(noElExists('.modal'));
        action.invoke();
        assert(oneElExists('.modal'));
      });

      describe("when the confirmation model is ok'ed", function() {
        it("should issue a conversation action request to the appropriate url",
        function(done) {
          server.respondWith(function(req) {
            assert.equal(req.url, '/conversation/action');
            done();
          });

          action.invoke();
          $('.modal [data-handler=1]').click();
          server.respond();
        });
      });
    });
  });
});
