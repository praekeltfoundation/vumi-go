describe("go.components.actions", function() {
  var actions = go.components.actions;

  describe("ActionView", function() {
    var ActionView = actions.ActionView;

    var ToyActionView = ActionView.extend({
      invoke: function() { this.trigger('invoke'); }
    });

    var action;

    beforeEach(function() {
      action = new ToyActionView();
    });

    describe("when it is clicked", function() {
      it("should invoke its own action", function(done) {
        action.on('invoke', function() { done(); });
        action.$el.click();
      });
    });
  });

  describe("CallActionView", function() {
    var CallActionView = actions.CallActionView;

    var action;

    beforeEach(function() {
      action = new CallActionView();

      action.$el
        .attr('data-url', '/hypothetical-basking-shark')
        .attr('data-action', 'start')
        .attr('data-id', 'something');
    });

    describe(".invoke", function() {
      var server;

      beforeEach(function() {
        server = sinon.fakeServer.create();
      });

      afterEach(function() {
        server.restore();
      });

      it("should send an ajax request", function(done) {
        server.respondWith(function(req) {
          assert.deepEqual(
            JSON.parse(req.requestBody),
            {action: 'start', id: 'something'});

          done();
        });

        action.invoke();
        server.respond();
      });

      it("should emit an 'invoke' event", function(done) {
        action.on('invoke', function() { done(); });
        action.invoke();
      });

      describe("when the ajax request is successful", function() {
        it("call the original success callback", function(done) {
          server.respondWith('{}');
          action.ajax = {success: function() { done(); }};

          action.invoke();
          server.respond();
        });

        it("should trigger a 'success' event", function(done) {
          server.respondWith('{}');
          action.on('success', function() { done(); });

          action.invoke();
          server.respond();
        });
      });

      describe("when the ajax request is unsuccessful", function() {
        it("call the original error callback", function(done) {
          server.respondWith([400, {}, '']);
          action.ajax = {error: function() { done(); }};

          action.invoke();
          server.respond();
        });

        it("should trigger an 'error' event", function(done) {
          server.respondWith([400, {}, '']);
          action.on('error', function() { done(); });

          action.invoke();
          server.respond();
        });
      });
    });
  });
});
