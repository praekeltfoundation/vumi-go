describe("go.components.actions", function() {
  var actions = go.components.actions;

  var Model = go.components.models.Model;

  var testHelpers = go.testHelpers,
      assertRequest = testHelpers.rpc.assertRequest,
      response = testHelpers.rpc.response;

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

  describe("SaveActionView", function() {
    var SaveActionView = actions.SaveActionView;

    var ToyModel = Model.extend({
      url: '/test',

      methods: {
        create: {method: 's', params: ['a', 'b']}
      }
    });

    var action;

    beforeEach(function() {
      action = new SaveActionView({
        model: new ToyModel({a: 'foo', b: 'bar'})
      });
    });

    describe(".invoke", function() {
      var server;

      beforeEach(function() {
        server = sinon.fakeServer.create();
      });

      afterEach(function() {
        server.restore();
      });

      it("should emit an 'invoke' event", function(done) {
        action.on('invoke', function() { done(); });
        action.invoke();
      });

      it("should send its model's data to the server", function(done) {
        server.respondWith(function(req) {
          assertRequest(req, '/test', 's', ['foo', 'bar']);
          done();
        });

        action.invoke();
        server.respond();
      });

      describe("when the request is successful", function() {
        it("should emit a 'success' event", function(done) {
          action.on('success', function() { done(); });
          server.respondWith(response());

          action.invoke();
          server.respond();
        });
      });

      describe("when the request is not successful", function() {
        it("should emit a 'failure' event", function(done) {
          action.on('error', function() { done(); });
          server.respondWith([400, {}, '']);

          action.invoke();
          server.respond();
        });
      });
    });
  });

  describe("ResetActionView", function() {
    var ResetActionView = actions.ResetActionView;

    var action;

    beforeEach(function() {
      action = new ResetActionView({
        model: new Model({a: 'foo', b: 'bar'})
      });
    });

    describe(".invoke", function() {
      it("should emit an 'invoke' event", function(done) {
        action.on('invoke', function() { done(); });
        action.invoke();
      });

      it("should reset its model to its initial state", function() {
        action.model.set('a', 'larp');
        assert.deepEqual(action.model.toJSON(), {a: 'larp', b: 'bar'});

        action.invoke();
        assert.deepEqual(action.model.toJSON(), {a: 'foo', b: 'bar'});
      });
    });
  });

  describe("CallActionView", function() {
    var CallActionView = actions.CallActionView;

    var ToyCallActionView = CallActionView.extend({
      data: function() {
        return {
          id:  this.$el.attr('data-id'),
          action: this.$el.attr('data-action')
        };
      }
    });

    var action;

    beforeEach(function() {
      action = new ToyCallActionView();

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
            req.requestBody,
            'id=something&action=start');

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

      describe("when the ajax request is not successful", function() {
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
