describe("go.components.views", function() {
  var testHelpers = go.testHelpers,
      oneElExists = testHelpers.oneElExists;

  var views = go.components.views;

  beforeEach(function() {
    $('body').append("<div id='dummy'></div>");
  });

  afterEach(function() {
    $('#dummy').remove();
  });

  describe(".LabelView", function() {
    var LabelView = views.LabelView;

    var label;

    var assertOffset = function(el, expectedOffset) {
      var offset = $(el).offset();
      assert.closeTo(offset.top, expectedOffset.top, 1);
      assert.closeTo(offset.left, expectedOffset.left, 1);
    };

    beforeEach(function() {
      $('#dummy')
        .width(200)
        .height(300)
        .css('position', 'absolute')
        .offset({left: 50, top: 100});

      label = new LabelView({
        my: 'right bottom',
        at: 'left top',
        of: $('#dummy'),
        text: 'foo'
      });
    });

    describe(".render", function() {
      it("should attach the label to the element", function() {
        label.render();
        assert(oneElExists('#dummy .label'));
      });

      it("should position the label at the given position", function() {
        label.render();
        assertOffset('#dummy .label', {left: 21, top: 73});
      });

      it("should render the given text", function() {
        label.render();
        assert.equal($('#dummy .label').text(), 'foo');
      });
    });
  });
});
