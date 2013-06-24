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

  describe(".assertModelAttrs", function() {
    var assertModelAttrs = testHelpers.assertModelAttrs;

    var models = go.components.models,
        Model = models.Model;

    var ToyModel = Model.extend({
      relations: [{
        type: Backbone.HasMany,
        key: 'submodels',
        relatedModel: Model
      }]
    });

    it("should determine whether a model has only the given attrs", function() {
      assertModelAttrs(new ToyModel({
        uuid: 'jimmy',
        a: 'red',
        b: 'blue',
        c: 'green',
        submodels: [
          {uuid: 'one', spoon: 'yes'},
          {uuid: 'two', spoon: 'pen'}]
      }), {
        uuid: 'jimmy',
        a: 'red',
        b: 'blue',
        c: 'green',
        submodels: [
          {uuid: 'one', spoon: 'yes'},
          {uuid: 'two', spoon: 'pen'}]
      });

      assertFails(function() {
        assertModelAttrs(new ToyModel({
          uuid: 'sam',
          a: 'red',
          b: 'blue',
          c: 'green',
          submodels: [
            {uuid: 'one', spoon: 'yes'},
            {uuid: 'two', spoon: 'pen'}]
        }), {
          uuid: 'sam',
          a: 'red',
          b: 'blue',
          c: 'green',
          submodels: [
            {uuid: 'one', spoon: 'yes'},
            {uuid: 'two', spoon: 'rawr'}]
        });
      });
    });
  });
});
