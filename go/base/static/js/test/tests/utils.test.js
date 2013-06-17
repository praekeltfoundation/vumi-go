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

  describe(".ensureObject", function() {
    var ensureObject = go.utils.ensureObject;

    it("should get the object by name if a string was given", function() {
      assert.equal(
        ensureObject('thing.subthing', {thing: {subthing: 23}}),
        23);
    });

    it("should return what it was given if it was a non-string", function() {
      assert.equal(ensureObject(23), 23);
    });
  });

  describe(".switchViews", function() {
    var switchViews = go.utils.switchViews;

    var ToyView = Backbone.View.extend({
    });

    var $dummy = $("<div id='dummy'></div>");

    beforeEach(function() {
      $('body').append($dummy);
    });

    afterEach(function() {
      $('#dummy').remove();
    });

    it("should replace the `from` element with the `to` element in the DOM",
    function() {
      var from = new ToyView({id: 'from'}),
          to = new ToyView({id: 'to'});

      from.render();
      to.render();
      $dummy.append(from.$el);

      assert(oneElExists('#dummy #from'));
      assert(noElExists('#dummy #to'));

      switchViews(from, to);

      assert(oneElExists('#dummy #to'));
      assert(noElExists('#dummy #from'));
    });
  });
});
