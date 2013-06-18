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

  describe(".MessageTextView", function() {
    var $div = $('<div/>');
    var text = 'Margle. The. World.';
    var $textarea = $('<textarea>' + text + '</textarea>');
    $div.append($textarea);
    var view = new go.components.views.MessageTextView({el: $textarea});

    it("should append an element `.textarea-char-count`", function() {
        $textarea.trigger('keyup');
        assert.equal($div.find('.textarea-char-count').length, 1);
    });

    it("should update char and SMS counters on keyup.", function() {
        $textarea.trigger('keyup');        
        assert.equal(text.length, view.totalChars);
        assert.equal(Math.ceil(text.length/160), view.totalSMS);

        text = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec quis tortor magna. Sed tristique mattis lectus sed tristique. Proin et diam id libero ullamcorper rhoncus. Cras bibendum aliquet faucibus. Maecenas nunc neque, laoreet sed bibendum eget, ullamcorper nec dui. Nam tortor quam, convallis dignissim auctor id, vehicula in nisl. Aenean accumsan, ipsum ac tristique interdum, leo quam pretium magna, nec sollicitudin ante ligula et sem. Aliquam a nulla orci. Curabitur vitae tortor nibh, id vulputate nisi. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae;';
        $textarea.val(text);
        $textarea.trigger('keyup');
        assert.equal(text.length, view.totalChars);
        assert.equal(Math.ceil(text.length/160), view.totalSMS);
    });
  });

});
