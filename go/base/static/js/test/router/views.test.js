describe("go.router.views", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists;
      oneElExists = testHelpers.oneElExists;

  describe("RouterActionView", function() {
    var RouterActionView = go.router.views.RouterActionView;

    var action,
        server;

    beforeEach(function() {
      server = sinon.fakeServer.create();
      action = new RouterActionView({
        el: $('<button>')
          .attr('data-url', '/router/action')
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
        it("should issue a router action request to the appropriate url",
        function(done) {
          server.respondWith(function(req) {
            assert.equal(req.url, '/router/action');
            done();
          });

          action.invoke();
          $('.modal [data-bb-handler=confirm]').click();
          server.respond();
        });
      });
    });
  });
});
