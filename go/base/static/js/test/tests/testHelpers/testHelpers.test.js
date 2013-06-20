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
  });

  describe(".noElExists", function() {
    var noElExists = testHelpers.noElExists;

    it("should determine whether no element exists", function() {
      assert(noElExists('.kjhfsdfsdf'));
      assert(!noElExists('#a'));
    });
  });
});
