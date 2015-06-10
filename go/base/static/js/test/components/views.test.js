describe("go.components.views", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists,
      oneElExists = testHelpers.oneElExists;

  var views = go.components.views;

  var ViewCollection = go.components.structures.ViewCollection,
      TemplateView = views.TemplateView;

  var ToyView = Backbone.View.extend({
    initialize: function(options) {
      this.thing = options.thing;
    },

    render: function() {
      this.$el.text(this.thing);
    }
  });

  beforeEach(function() {
    $('body').append("<div id='dummy'></div>");
  });

  afterEach(function() {
    $('#dummy').remove();
  });

  describe(".MessageTextView", function() {
    var $div = $('<div/>');
    var short_text = 'Margle. The. World.';
    var long_text = [
        'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec quis',
        ' tortor magna. Sed tristique mattis lectus sed tristique. Proin et',
        ' diam id libero ullamcorper rhoncus. Cras bibendum aliquet faucibus.',
        ' Maecenas nunc neque, laoreet sed bibendum eget, ullamcorper nec',
        ' dui. Nam tortor quam, convallis dignissim auctor id, vehicula in',
        ' nisl. Aenean accumsan, ipsum ac tristique interdum, leo quam',
        ' pretium magna, nec sollicitudin ante ligula et sem. Aliquam a nulla',
        ' orci. Curabitur vitae tortor nibh, id vulputate nisi. Vestibulum',
        ' ante ipsum primis in faucibus orci luctus et ultrices posuere',
        ' cubilia Curae;',
    ].join("");
    var $textarea = $('<textarea>' + short_text + '</textarea>');
    $div.append($textarea);
    var view = new go.components.views.MessageTextView({el: $textarea});

    function assert_char_counts(text, non_ascii) {
        var total_chars = text.length;
        var total_bytes = text.length * (1 + non_ascii);
        var total_smses = (Math.ceil(total_bytes / 160));
        var non_ascii_chars = go.utils.non_ascii(text);
        assert.equal(non_ascii, view.containsNonAscii);
        assert.equal(total_chars, view.totalChars);
        assert.equal(total_smses, view.totalSMS);
        assert.equal(total_bytes, view.totalBytes);
        var p = $div.find('.textarea-char-count').html();
        if (!non_ascii) {
            assert.equal(p, [
                total_chars + ' characters used',
                total_smses + ' smses',
            ].join('<br>'))
        }
        else {
            assert.equal(p, [
                'Non-ASCII characters: ' + non_ascii_chars.join(', '),
                total_chars + ' characters used (~' + total_bytes + ' bytes)',
                total_smses + ' smses',
            ].join('<br>'))
        }
    }

    it("should append an element `.textarea-char-count`", function() {
        $textarea.trigger('keyup');
        assert.equal($div.find('.textarea-char-count').length, 1);
    });

    it("should update char and SMS counters on keyup.", function() {
        $textarea.trigger('keyup');
        assert_char_counts(short_text, false);

        $textarea.val(long_text);
        $textarea.trigger('keyup');
        assert_char_counts(long_text, false);
    });

    it("should detect non-ASCII characters", function() {
        var non_ascii_text = short_text + "ó";
        $textarea.val(non_ascii_text);
        $textarea.trigger('keyup');
        assert_char_counts(non_ascii_text, true);
    });
  });

  describe(".ConfirmView", function() {
    var ConfirmView = views.ConfirmView;

    var confirm;

    beforeEach(function() {
      confirm = new ConfirmView({
        content: 'I am a modal.',
        optional: true,
        animate: false
      });
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
      beforeEach(function() {
        confirm.render();
      });

      it("should trigger an 'ok' event", function(done) {
        confirm.on('ok', function() { done(); });
        confirm.$('.ok').click();
      });

      it("should hide the modal", function(done) {
        confirm.$el.on('hidden.bs.modal', function() { done(); });
        confirm.$('.ok').click();
      });
    });

    describe("when the 'cancel' button is clicked", function() {
      beforeEach(function() {
        confirm.render();
      });

      it("should trigger a 'cancel' event", function(done) {
        confirm.on('cancel', function() { done(); });
        confirm.$('.cancel').click();
      });

      it("should hide the modal", function(done) {
        confirm.$el.on('hidden.bs.modal', function() { done(); });

        confirm.$('.cancel').click();
      });
    });

    describe("on 'ok' events", function() {
      it("should unbind 'ok' and 'cancel' callbacks", function() {
        var i = 0;
        confirm.on('ok', function() { i++ && assert.fail(); });
        confirm.on('cancel', function() { assert.fail(); });

        confirm.trigger('ok');

        // No callbacks should be invoked now
        confirm.trigger('ok');
        confirm.trigger('cancel');
      });
    });

    describe("on 'cancel' events", function() {
      it("should unbind 'ok' and 'cancel' callbacks", function() {
        var i = 0;
        confirm.on('ok', function() { assert.fail(); });
        confirm.on('cancel', function() { i++ && assert.fail(); });

        confirm.trigger('cancel');

        // No callbacks should be invoked now
        confirm.trigger('cancel');
        confirm.trigger('ok');
      });
    });
  });

  describe(".PopoverView", function() {
    var PopoverView = views.PopoverView;

    var ToyPopoverView = PopoverView.extend({
      render: function() { this.$el.text('Put away those fiery biscuits.'); }
    });

    var popover;

    beforeEach(function() {
      popover = new ToyPopoverView({
        target: $('#dummy'),
        bootstrap: {animation: false}
      });
    });

    afterEach(function() {
      popover.remove();
    });

    describe(".show", function() {
      it("should show the popover", function() {
        assert(noElExists('.popover'));
        popover.show();
        assert(oneElExists('.popover'));
      });

      it("render the view as the contents of the popover", function() {
        assert.equal($('.popover-content').text(), '');

        popover.show();

        assert.equal(
          $('.popover-content').text(),
          'Put away those fiery biscuits.');
      });

      it("should trigger a 'show' event", function(done) {
        popover
          .on('show', function() { done(); })
          .show();
      });
    });

    describe(".hide", function() {
      beforeEach(function() {
        popover.show();
      });

      it("should hide the popover", function() {
        assert(oneElExists('.popover'));
        popover.hide();
        assert(noElExists('.popover'));
      });

      it("should trigger a 'hide' event", function(done) {
        popover
          .on('hide', function() { done(); })
          .hide();
      });
    });

    describe(".toggle", function() {
      it("should show the popover if it is hidden", function() {
        assert(noElExists('.popover'));
        popover.toggle();
        assert(oneElExists('.popover'));
      });

      it("should hide the popover if it is not hidden", function() {
        popover.show();

        assert(oneElExists('.popover'));
        popover.toggle();
        assert(noElExists('.popover'));
      });
    });
  });

  describe(".Partials", function() {
    var Partials = views.Partials;

    var partials;

    beforeEach(function() {
      partials = new Partials({
        a: _.template('<div>a</div>'),
        b: new ToyView({thing: 'b'}),
        c: [
          _.template('<div>c1</div>'),
          _.template('<div>c2</div>')],
        d: new ViewCollection({
          type: ToyView,
          views: [
            {thing: 'd1'},
            {thing: 'd2'}]
        })
      });
    });

    describe(".toPlaceholders", function() {
      it("should convert the partials to placeholders", function() {
        assert.deepEqual(partials.toPlaceholders(), {
          a: ['<div data-partial="a" data-partial-index="0"></div>'],
          b: ['<div data-partial="b" data-partial-index="0"></div>'],
          c: ['<div data-partial="c" data-partial-index="0"></div>',
              '<div data-partial="c" data-partial-index="1"></div>'],
          d: ['<div data-partial="d" data-partial-index="0"></div>',
              '<div data-partial="d" data-partial-index="1"></div>']
        });
      });
    });

    describe(".applyPartial", function() {
      it("should apply its partials to the target", function() {
        var $target = $([
          '<div>',
            '<div data-partial="a" data-partial-index="0"></div>',
            '<div data-partial="b" data-partial-index="0"></div>',
            '<div data-partial="c" data-partial-index="0"></div>', 
            '<div data-partial="c" data-partial-index="1"></div>', 
            '<div data-partial="d" data-partial-index="0"></div>', 
            '<div data-partial="d" data-partial-index="1"></div>', 
          '</div>'
        ].join(''));

        partials.applyTo($target);

        assert.equal($target.html(), [
          '<div>a</div>',
          '<div>b</div>',
          '<div>c1</div>',
          '<div>c2</div>',
          '<div>d1</div>',
          '<div>d2</div>'
        ].join(''));
      });
    });
  });

  describe(".TemplateView", function() {
    describe(".render", function() {
      it("should apply the jst template", function()  {
        var template = new TemplateView({
          jst: _.template('I am the <%= thing %>.'),
          data: {thing: 'Walrus'}
        });

        assert.equal(template.$el.html(), '');
        template.render();
        assert.equal(template.$el.html(), 'I am the Walrus.');
      });

      it("should apply its view partials", function() {
        var template = new TemplateView({
          jst: _.template([
            '<%= partials.p1 %>',
            '<%= partials.p2 %>'
          ].join('')),

          partials: {
            p1: new ToyView({thing: 'Walrus'}),
            p2: new ToyView({thing: 'Eggman'})
          }
        });

        template.render();

        assert.equal(
          template.$el.html(), [
          '<div>Walrus</div>',
          '<div>Eggman</div>'
        ].join(''));
      });

      it("should ensure its view partials keep their delegated events",
      function(done) {
        var i = 0;

        var p = new Backbone.View({
          tagName: 'button',
          events: {'click': function() { i++ && done(); }}
        });

        var template = new TemplateView({
          jst: _.template('<%= partials.p %>'),
          partials: {p: p}
        });

        template.render();
        p.$el.click();

        template.render();
        p.$el.click();
      });

      it("should apply its template function partials", function() {
        var template = new TemplateView({
          jst: _.template([
            '<%= partials.p1 %>',
            '<%= partials.p2 %>'
          ].join('')),

          partials: {
            p1: _.template('<div>I am the Eggman</div>'),
            p2: _.template('<div>They are the Eggmen</div>')
          }
        });

        template.render();

        assert.equal(
          template.$el.html(), [
          '<div>I am the Eggman</div>',
          '<div>They are the Eggmen</div>'
        ].join(''));
      });

      it("should apply its view collection partials", function() {
        var template = new TemplateView({
          jst: _.template([
            '<%= partials.p[0] %>',
            '<%= partials.p[1] %>'
          ].join('')),

          partials: {
            p: new ViewCollection({
              type: ToyView,
              views: [{thing: 'Walrus'}, {thing: 'Eggman'}]
            })
          }
        });

        template.render();

        assert.equal(
          template.$el.html(), [
          '<div>Walrus</div>',
          '<div>Eggman</div>'
        ].join(''));
      });

      it("should apply its list partials", function() {
        var template = new TemplateView({
          jst: _.template([
            '<%= partials.p[0] %>',
            '<%= partials.p[1] %>'
          ].join('')),

          partials: {
            p: [
              new ToyView({thing: 'Walrus'}),
              new ToyView({thing: 'Eggman'})
            ]
          }
        });

        template.render();

        assert.equal(
          template.$el.html(), [
          '<div>Walrus</div>',
          '<div>Eggman</div>'
        ].join(''));
      });
    });
  });
});
