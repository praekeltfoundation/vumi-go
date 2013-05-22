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

  describe(".parent", function() {
    var Extendable = go.components.structures.Extendable,
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
});
