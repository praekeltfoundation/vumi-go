describe("go.utils", function() {
  var testHelpers = go.testHelpers,
      oneElExists = testHelpers.oneElExists,
      noElExists = testHelpers.noElExists;

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

  describe(".objectByName", function() {
    var objectByName = go.utils.objectByName;

    it("should get an object defined directly on the context object",
    function() {
      assert.equal(objectByName('thing', {thing: 3}), 3);
    });

    it("should get an object defined on a property of the context object",
    function() {
      assert.equal(
        objectByName('thing.subthing', {thing: {subthing: 23}}),
        23);
    });
  });

  describe(".maybeByName", function() {
    var maybeByName = go.utils.maybeByName;

    it("should get the object by name if a string was given", function() {
      assert.equal(
        maybeByName('thing.subthing', {thing: {subthing: 23}}),
        23);
    });

    it("should return what it was given if it was a non-string", function() {
      assert.equal(maybeByName(23), 23);
    });
  });
});
