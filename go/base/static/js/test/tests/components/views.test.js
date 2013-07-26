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
        popover: {animation: false}
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
        assert(noElExists('.popover-content'));

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

  describe(".TemplateView", function() {
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
            '<script data-partial="p1" type="partial"></script>',
            '<script data-partial="p2" type="partial"></script>'
          ].join('')),

          partials: {
            p1: new ToyView({thing: 'Walrus'}),
            p2: new ToyView({thing: 'Eggman'})
          }
        });

        template.render();

        assert.equal(
          template.$el.html(), [
          '<div data-partial="p1">Walrus</div>',
          '<div data-partial="p2">Eggman</div>'
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
          jst: _.template('<script data-partial="p"></script>'),
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
            '<script data-partial="p1" type="partial"></script>',
            '<script data-partial="p2" type="partial"></script>'
          ].join('')),

          partials: {
            p1: _.template('<div>I am the Eggman</div>'),
            p2: _.template('<div>They are the Eggmen</div>')
          }
        });

        template.render();

        assert.equal(
          template.$el.html(), [
          '<div data-partial="p1">I am the Eggman</div>',
          '<div data-partial="p2">They are the Eggmen</div>'
        ].join(''));
      });

      it("should apply its view collection partials", function() {
        var template = new TemplateView({
          jst: _.template([
            '<script data-partial="p"></script>',
            '<script data-partial="p"></script>'
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
          '<div data-partial="p">Walrus</div>',
          '<div data-partial="p">Eggman</div>'
        ].join(''));
      });

      it("should apply its list partials", function() {
        var template = new TemplateView({
          jst: _.template([
            '<script data-partial="p"></script>',
            '<script data-partial="p"></script>'
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
          '<div data-partial="p">Walrus</div>',
          '<div data-partial="p">Eggman</div>'
        ].join(''));
      });
    });
  });
});
