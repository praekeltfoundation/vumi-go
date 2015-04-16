describe("go.components.actions", function() {
  var actions = go.components.actions;

  var Model = go.components.models.Model;

  var testHelpers = go.testHelpers,
      assertRequest = testHelpers.rpc.assertRequest,
      response = testHelpers.rpc.response,
      noElExists = testHelpers.noElExists,
      oneElExists = testHelpers.oneElExists;

  describe("PopoverNotifierView", function() {
    var ActionView = actions.ActionView,
        PopoverNotifierView = actions.PopoverNotifierView;

    var action,
        notifier;

    beforeEach(function() {
      action = new ActionView({name: 'Crimp'});
      notifier = new PopoverNotifierView({
        delay: 0,
        busyWait: 0,
        action: action,
        bootstrap: {
          container: 'body',
          animation: false
        }
      });

      sinon.stub(
        JST,
        'components_notifiers_popover_busy',
        function() { return 'busy'; });
    });

    afterEach(function() {
      JST.components_notifiers_popover_busy.restore();
      action.remove();
      notifier.remove();
    });

    describe("when the action is invoked", function() {
      it("should show a notification", function() {
        assert(noElExists('.popover'));
        assert.equal(notifier.$el.text(), '');

        action.trigger('invoke');

        assert(oneElExists('.popover'));
        assert.equal(notifier.$el.text(), 'busy');
      });

      it("set the appropriate class name on the popover element", function() {
        var $popover = notifier.popover.tip();

        assert(!$popover.hasClass('notifier'));
        assert(!$popover.hasClass('success'));
        assert(!$popover.hasClass('error'));
        assert(!$popover.hasClass('info'));

        action.trigger('invoke');

        assert(!$popover.hasClass('success'));
        assert(!$popover.hasClass('error'));
        assert($popover.hasClass('notifier'));
        assert($popover.hasClass('info'));
      });
    });

    describe("when the action is successful", function() {
      beforeEach(function() {
        action.trigger('invoke');
      });

      it("should show a notification", function() {
        action.trigger('success');
        assert.include(notifier.$el.text(), 'Crimp successful.');
      });

      it("set the appropriate class name on the popover element", function() {
        var $popover = notifier.popover.tip();

        assert(!$popover.hasClass('success'));
        assert(!$popover.hasClass('error'));
        assert($popover.hasClass('notifier'));
        assert($popover.hasClass('info'));

        action.trigger('success');

        assert(!$popover.hasClass('error'));
        assert(!$popover.hasClass('info'));
        assert($popover.hasClass('notifier'));
        assert($popover.hasClass('success'));
      });
    });

    describe("when the action is unsuccessful", function() {
      beforeEach(function() {
        action.trigger('invoke');
      });

      it("should show a notification", function() {
        action.trigger('error');
        assert.include(notifier.$el.text(), 'Crimp failed.');
      });

      it("set the appropriate class name on the popover element", function() {
        var $popover = notifier.popover.tip();

        assert(!$popover.hasClass('success'));
        assert(!$popover.hasClass('error'));
        assert($popover.hasClass('notifier'));
        assert($popover.hasClass('info'));

        action.trigger('error');

        assert(!$popover.hasClass('success'));
        assert(!$popover.hasClass('info'));
        assert($popover.hasClass('notifier'));
        assert($popover.hasClass('error'));
      });
    });

    describe("when '.close' is clicked", function() {
      beforeEach(function() {
        action.trigger('success');
      });

      it("should close the popover", function() {
        assert(oneElExists('.popover'));
        notifier.$('.close').click();
        assert(noElExists('.popover'));
      });
    });
  });

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

      it("should reset its model to its initial state", function(done) {
        action.model.set('a', 'larp');
        assert.deepEqual(action.model.toJSON(), {a: 'larp', b: 'bar'});

        action.invoke();

        action.once('success', function() {
          assert.deepEqual(action.model.toJSON(), {a: 'foo', b: 'bar'});
          done();
        });
      });
    });
  });
});
