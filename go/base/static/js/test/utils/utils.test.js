describe("go.utils", function() {
  describe(".idOf", function() {
    var idOf = go.utils.idOf,
        GoError = go.errors.GoError,
        v;

    beforeEach(function() {
      $('body').append("<div class='dummy'></div>");
      $('.dummy').html("<div id='v'></div>");
      v = new Backbone.View({el: '.dummy #v'});
    });

    afterEach(function() { $('body').remove('.dummy'); });

    it("get the element id given a Backbone view", function() {
      assert.equal(idOf(v), 'v');
    });

    it("get the element id given a selector", function() {
      assert.equal(idOf('.dummy #v'), 'v');
    });

    it("get the element id given an element", function() {
      assert.equal(idOf($('.dummy #v').get(0)), 'v');
    });

    it("get the element id given a jquery wrapped element", function() {
      assert.equal(idOf($('.dummy #v')), 'v');
    });

    it("should throw an error if the element is not found", function() {
      assert.throws(function() { idOf($('.dummy #non-existent')); }, GoError);
    });

    it("should throw an error if the element has no id", function() {
      $('.dummy').append("<div class='no-id'></div>");
      assert.throws(function() { idOf($('.dummy .no-id')); }, GoError);
    });
  });
});
