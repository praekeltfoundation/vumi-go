describe("go.utils", function() {
  describe(".Extendable", function() {
    var Extendable = go.utils.Extendable;

    it("should set up the prototype chain correctly", function() {
      var Parent = Extendable.extend(),
          Child = Parent.extend();

       var child = new Child();
       assert.instanceOf(child, Parent);
       assert.instanceOf(child, Child);
    });

    it("should use a constructor function if specified", function() {
      var Thing = Extendable.extend({
        constructor: function (name) { this.name = name; }
      });

      assert.equal(new Thing('foo').name, 'foo');
    });

    it("should default to a parent's constructor", function() {
      var Parent,
          Child;

      Parent = Extendable.extend({
        constructor: function (name) { this.name = name; }
      });
      Child = Parent.extend();

      assert.equal(new Child('foo').name, 'foo');
    });

    it("should accept multiple object arguments", function() {
      var Thing = Extendable.extend({'a': 'one'}, {'b': 'two'}),
          thing = new Thing();

      assert.equal(thing.a, 'one');
      assert.equal(thing.b, 'two');
    });
  });

  describe("._super_", function() {
    var Extendable = go.utils.Extendable,
        _super_ = go.utils._super_;

    it("should provide the 'super' prototype", function() {
      var Parent = Extendable.extend(),
          Child = Parent.extend();

      assert.equal(_super_(new Child()), Parent.prototype);
    });

    it("should provide a property on the 'super' prototype", function() {
      var Parent = Extendable.extend({prop: 23}),
          Child = Parent.extend({prop: 22});

      assert.equal(_super_(new Child(), 'prop'), 23);
    });

    it("should provide binded versions of the 'super' prototype's functions",
       function() {
      var Parent = Extendable.extend({fn: function() { return this; }}),
          Child = Parent.extend({fn: function() { return 22; }}),
          child = new Child();

      assert.equal(_super_(child, 'fn')(), child);
    });
  });
  describe(".delegateEvents", function() {
    var Eventable = go.utils.Eventable,
        delegateEvents = go.utils.delegateEvents;

    it("should call callbacks when their events are emitted", function(done) {
      var Thing,
          thing,
          aCalled = false,
          bCalled = false,
          maybeDone = function() { aCalled && bCalled && done(); };
      
      Thing = Eventable.extend({
        a: function() {
          aCalled = true;
          maybeDone();
        },
        b: function() {
          bCalled = true;
          maybeDone();
        }
      });

      thing = new Thing();
      delegateEvents(thing, {'event-a': 'a', 'event-b': 'b'});
      thing.trigger('event-a');
      thing.trigger('event-b');
    });

    it("should bind callbacks to the Eventable instance", function(done) {
      var Thing,
          thing;
      
      Thing = Eventable.extend({
        callback: function() {
          assert.equal(this, thing);
          done();
        }
      });

      thing = new Thing();
      delegateEvents(thing, {'event': 'callback'});
      thing.trigger('event');
    });
  });
});
