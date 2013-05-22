describe("go.utils", function() {
  describe(".merge", function() {
    var merge = go.utils.merge;

    it("should merge objects together into a single object", function() {
      assert.deepEqual(
        merge({a: 1}, {b: 2, c: 3}, {d: 4}),
        {a: 1, b: 2, c: 3, d: 4});

      assert.deepEqual(
        merge({a: 1}, {}, {d: 4}),
        {a: 1, d: 4});

      assert.deepEqual(
        merge({a: 1}, {b: 2}, {a: 'one'}),
        {a: 'one', b: 2});
    });

    it("should not modify any of the passed in objects", function() {
      var a = {a: 1},
          b = {b: 2},
          c = {c: 3};

      merge(a, b, c);

      assert.deepEqual(a, {a: 1});
      assert.deepEqual(b, {b: 2});
      assert.deepEqual(c, {c: 3});
    });
  });

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

  describe(".parent", function() {
    var Extendable = go.utils.Extendable,
        parent = go.utils.parent;

    it("should provide the 'super' prototype", function() {
      var Parent = Extendable.extend(),
          Child = Parent.extend();

      assert.equal(parent(new Child()), Parent.prototype);
    });

    it("should provide a property on the 'super' prototype", function() {
      var Parent = Extendable.extend({prop: 23}),
          Child = Parent.extend({prop: 22});

      assert.equal(parent(new Child(), 'prop'), 23);
    });

    it("should provide binded versions of the 'super' prototype's functions",
       function() {
      var Parent = Extendable.extend({fn: function() { return this; }}),
          Child = Parent.extend({fn: function() { return 22; }}),
          child = new Child();

      assert.equal(parent(child, 'fn')(), child);
    });
  });

  describe(".pairId", function() {
    var pairId = go.utils.pairId;

    it("should create a unique id from a pair of ids", function() {
      assert.equal(pairId(1, 2), '1-2');
      assert.equal(pairId(2, 1), '1-2');

      assert.equal(pairId('a', 'b'), 'a-b');
      assert.equal(pairId('b', 'a'), 'a-b');
    });
  });
});
