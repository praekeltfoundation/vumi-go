describe("go.components.views", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists;
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
        assertOffset('#dummy .label', {left: 19, top: 80});
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

  describe(".ConfirmView", function() {
    var ConfirmView = views.ConfirmView;

    var confirm;

    beforeEach(function() {
      confirm = new ConfirmView({
        content: 'I am a modal.',
        optional: true
      });

      // Remove animation to make phantomjs happy
      // ('shown' and 'hidden' events don't seem to be triggered otherwise)
      confirm.$el.removeClass('fade in');
    });

    afterEach(function() {
      confirm.remove();
    });

    describe(".render", function() {
      it("should show the modal", function() {
        assert(noElExists('.modal'));
        confirm.render();
        assert(oneElExists('.modal'));
      });
    });

    describe(".show", function() {
      it("should show the modal", function() {
        assert(noElExists('.modal'));
        confirm.show();
        assert(oneElExists('.modal'));
      });

      it("should not show the modal once the user has disabled the modal",
      function() {
        confirm.show();
        assert(!confirm.$el.is(':hidden'));
        confirm.$('.dont-show').click();
        confirm.$('.ok').click();

        assert(confirm.$el.is(':hidden'));
        confirm.show();
        assert(confirm.$el.is(':hidden'));
      });

      it("should trigger an 'ok' event if the user has disabled the modal",
      function(done) {
        confirm.render();
        confirm.$('.dont-show').click();
        confirm.$('.ok').click();

        confirm.on('ok', function() { done(); });
        confirm.show();
      });
    });

    describe("when the 'ok' button is clicked", function() {
      beforeEach(function(done) {
        confirm.$el.on('shown', function() { done(); });
        confirm.render();
      });

      it("should trigger an 'ok' event", function(done) {
        confirm.on('ok', function() { done(); });
        confirm.$('.ok').click();
      });

      it("should hide the modal", function(done) {
        confirm.$el.on('hidden', function() { done(); });
        confirm.$('.ok').click();
      });
    });

    describe("when the 'cancel' button is clicked", function() {
      beforeEach(function(done) {
        confirm.$el.on('shown', function() { done(); });
        confirm.render();
      });

      it("should trigger a 'cancel' event", function(done) {
        confirm.on('cancel', function() { done(); });
        confirm.$('.cancel').click();
      });

      it("should hide the modal", function(done) {
        confirm.$el.on('hidden', function() { done(); });
        confirm.$('.cancel').click();
      });
    });
  });
});
