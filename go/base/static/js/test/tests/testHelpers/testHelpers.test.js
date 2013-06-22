describe("go.testHelpers", function() {
  var testHelpers = go.testHelpers,
      assertFails = testHelpers.assertFails;

  beforeEach(function() {
    $('body').append([
      "<div id='dummy'>",
        "<div id='a' class='thing'></div>",
        "<div id='b' class='thing'></div>",
        "<div id='c' class='different-thing'></div>",
      "</div>"
    ].join(''));

    Backbone.Relational.store.reset();
  });

  afterEach(function() {
    $('#dummy').remove();
  });

  describe(".oneElExists", function() {
    var oneElExists = testHelpers.oneElExists;

    it("should determine whether one element exists", function() {
      assert(oneElExists('#a'));
      assert(oneElExists('.different-thing'));

      assert(!oneElExists('.thing'));
      assert(!oneElExists('.kjhfsdfsdf'));
    });
  });

  describe(".noElExists", function() {
    var noElExists = testHelpers.noElExists;

    it("should determine whether no element exists", function() {
      assert(noElExists('.kjhfsdfsdf'));
      assert(!noElExists('#a'));
    });
  });

  describe(".attrsOfModel", function() {
    var attrsOfModel = testHelpers.attrsOfModel;

    var models = go.components.models,
        Model = models.Model;

    it("should return the model's attrs if a model was given", function() {
      assert.deepEqual(
        attrsOfModel(new Model({uuid: 'ackbar', a: 'red', b: 'blue'})),
        {uuid: 'ackbar', a: 'red', b: 'blue'});
    });

    it("should return the model's attrs an object was given", function() {
      assert.deepEqual(
        attrsOfModel({uuid: 'ackbar', a: 'red', b: 'blue', _rpcId: 132123}),
        {uuid: 'ackbar', a: 'red', b: 'blue'});
    });
  });

  describe(".assertModelAttrs", function() {
    var assertModelAttrs = testHelpers.assertModelAttrs;

    var models = go.components.models,
        Model = models.Model;

    it("should determine whether a model has only the given attrs", function() {
      assertModelAttrs(
        new Model({uuid: 'ackbar', a: 'red', b: 'blue'}),
        {uuid: 'ackbar', a: 'red', b: 'blue'});

      assertFails(function() {
        assertModelAttrs(
          new Model({uuid: 'anakin', a: 'red', b: 'blue'}),
          {uuid: 'ackbar', a: 'blue', b: 'green'});
      });
    });
  });
});
