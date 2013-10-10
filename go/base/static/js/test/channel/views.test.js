describe("go.channel.views", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists;
      oneElExists = testHelpers.oneElExists;

  describe("ChannelActionView", function() {
    var ChannelActionView = go.channel.views.ChannelActionView;

    var action,
        server;

    beforeEach(function() {
      server = sinon.fakeServer.create();
      action = new ChannelActionView({
        el: $('<button>')
          .attr('data-url', '/channel/action')
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
        it("should issue a channel action request to the appropriate url",
        function(done) {
          server.respondWith(function(req) {
            assert.equal(req.url, '/channel/action');
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
