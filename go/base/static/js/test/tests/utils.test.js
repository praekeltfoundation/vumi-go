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
      var Parent, Child;
      Parent = Extendable.extend({
        constructor: function (name) { this.name = name; }
      });
      Child = Parent.extend();

      assert.equal(new Child('foo').name, 'foo');
    });

    it("should provide a reference to parent prototype", function() {
      var Parent, Child;
      Parent = Extendable.extend({
        constructor: function (name) { this.name = name; }
      });
      Child = Parent.extend({
        constructor: function (name) { this.parent.constructor(name); }
      });

      assert.equal(new Child('foo').name, 'foo');
    });
  });

  describe(".Eventable", function() {
    var Eventable = go.utils.Eventable;

    it("should call callbacks when their events are emitted", function(done) {
      var Thing,
          thing,
          aCalled = false,
          bCalled = false,
          maybeDone = function() { aCalled && bCalled && done(); };
      
      Thing = Eventable.extend({
        events: {'event-a': 'a', 'event-b': 'b'},
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
      thing.trigger('event-a');
      thing.trigger('event-b');
    });

    it("should bind callbacks to the Eventable instance", function(done) {
      var Thing,
          thing;
      
      Thing = Eventable.extend({
        events: {'event': 'callback'},
        callback: function() {
          assert.equal(this, thing);
          done();
        }
      });

      thing = new Thing();
      thing.trigger('event');
    });
  });

  describe(".pop", function() {
    var pop = go.utils.pop;

    it("should pop a property off an object", function() {
      var obj = {a: 'one', b: 'two'};
      assert.equal(pop(obj, 'a'), 'one');
      assert.deepEqual(obj, {b: 'two'});
    });

    it("should handle non-existent properties without breaking", function() {
      var obj = {a: 'one'};
      assert.equal(pop({a: 'one'}, 'b'), undefined);
      assert.deepEqual(obj, {a: 'one'});
    });
  });
});
