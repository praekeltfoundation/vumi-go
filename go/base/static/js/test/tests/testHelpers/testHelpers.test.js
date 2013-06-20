describe("go.testHelpers", function() {
  var testHelpers = go.testHelpers;

  beforeEach(function() {
    $('body').append([
      "<div id='dummy'>",
        "<div id='a' class='thing'></div>",
        "<div id='b' class='thing'></div>",
        "<div id='c' class='different-thing'></div>",
      "</div>"
    ].join(''));
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

    describe(".withData", function() {
      beforeEach(function() {
        $('#dummy #a').data('r', '2');
        $('#dummy #a').data('d', '2');

        $('#dummy #b').data('r', '3');
      });

      it("should determine whether one element has any data with a key",
      function() {
        assert(oneElExists.withData('d'));

        assert(!oneElExists.withData('r'));
        assert(!oneElExists.withData('s'));
      });

      it("should determine whether one element has data with a key and value",
      function() {
        assert(oneElExists.withData('d', '2'));
        assert(!oneElExists.withData('d', '3'));
      });
    });
  });

  describe(".noElExists", function() {
    var noElExists = testHelpers.noElExists;

    it("should determine whether no element exists", function() {
      assert(noElExists('.kjhfsdfsdf'));
      assert(!noElExists('#a'));
    });

    describe(".withData", function() {
      beforeEach(function() {
        $('#dummy #a').data('r', '2');
      });

      it("should determine whether one element has any data with a key",
      function() {
        assert(noElExists.withData('s'));
        assert(!noElExists.withData('r'));
      });

      it("should determine whether one element has data with a key and value",
      function() {
        assert(noElExists.withData('r', '3'));
        assert(!noElExists.withData('r', '2'));
      });
    });
  });
});
