// go.components.views
// ===================
// Generic, re-usable views for Go

(function(exports) {
  var utils = go.utils,
      functor = utils.functor,
      maybeByName = utils.maybeByName;

  // A view that can be uniquely identified by its `uuid` property.
  var UniqueView = Backbone.View.extend({
    constructor: function(options) {
      options = options || {};
      Backbone.View.prototype.constructor.call(this, options);

      this.uuid = options.uuid || this.uuid || uuid.v4();

      // We need a way to uniquely identify a view (and its element) without
      // using its `id`, since this maps to the html id attribute. This causes
      // problems when set the id attribute to a uuid value which isn't a valid
      // html id attribute (for example, if it begins with a digit).
      this.$el.attr('data-uuid', _(this).result('uuid'));
    }
  });

  // View for a label which can be attached to an element.
  //
  // Options:
  //   - text: A string or a function returning a string containing the text to
  //   be displayed by the label
  //   - of: The target element this label should be attached to
  //   - my: The point on the label to align with the of
  //   - at: The point on the target element to align the label against
  var LabelView = Backbone.View.extend({
    tagName: 'span',
    className: 'label',

    initialize: function(options) {
      this.$of = $(options.of);
      this.text = functor(options.text);
      this.my = options.my;
      this.at = options.at;
    },

    render: function() {
      // Append the label to the of element so it can follow the of
      // around (in the case of moving or draggable ofs)
      this.$of.append(this.$el);

      this.$el
        .text(this.text())
        .position({
          of: this.$of,
          my: this.my,
          at: this.at
        })
        .css('position', 'absolute')
        .css('pointer-events', 'none');
    }
  });

  var MessageTextView = Backbone.View.extend({
    SMS_MAX_CHARS: 160,
    events: {
      'keyup': 'render'
    },
    initialize: function() {
      // we call render to output "0 characters used, 0 smses."
      this.render();
    },
    render: function() {
      var $p = this.$el.next();
      if (!$p.hasClass('textarea-char-count')) {
          $p = $('<p class="textarea-char-count"/>');
          this.$el.after($p);
      }
      this.totalChars = this.$el.val().length;
      this.totalSMS = Math.ceil(this.totalChars / this.SMS_MAX_CHARS);
      $p.html(this.totalChars + ' characters used<br>' + this.totalSMS + ' smses');

      return this;
    }
  });

  var ConfirmView = Backbone.View.extend({
    className: 'modal hide fade in',

    template: 'JST.components_confirm',

    events: {
      'click .ok': 'onOk',
      'click .cancel': 'onCancel'
    },

    optional: false,
    animated: true,

    initialize: function(options) {
      options = _(options || {}).defaults({
        optional: this.optional,
        animate: this.animated,
        content: ''
      });

      this.dontShow = false;
      this.content = options.content;
      this.optional = options.optional;
      this.animate(options.animate);

      this.resetActionHandlers();
    },

    resetActionHandlers: function() {
      this.off('ok');
      this.off('cancel');

      this.on('ok', this.resetActionHandlers, this);
      this.on('cancel', this.resetActionHandlers, this);
    },

    animate: function(animated) {
      if (animated) { this.$el.addClass('fade in'); }
      else { this.$el.removeClass('fade in'); }
    },

    onOk: function() {
      if (this.optional) {
        this.dontShow = this.$('.dont-show').is(':checked');
      }

      this.trigger('ok');
      this.hide();
    },

    onCancel: function() {
      this.trigger('cancel');
      this.hide();
    },

    show: function() {
      if (this.dontShow) { this.trigger('ok'); }
      else { this.render(); }
      return this;
    },

    hide: function() {
      this.$el.modal('hide');
      return this;
    },

    render: function() {
      this.$el
        .appendTo($('body'))
        .html(maybeByName(this.template)({self: this}))
        .modal('show');

      return this;
    }
  });

  var TemplateView = Backbone.View.extend({
    jst: _.template(''),

    partials: {},

    data: {},

    initialize: function(options) {
      if (options.data) { this.data = options.data; }

      if (options.jst) { this.jst = options.jst; }
      this.partials = _({}).extend(this.partials, options.partials || {});
    },

    renderPartial: function(name) {
      var partial = this.partials[name],
          $el;

      if (partial instanceof Backbone.View) {
        partial.render();
        $el = partial.$el;
      } else {
        $el = $(maybeByName(partial)(_(this).result('data')));
      }

      $el.attr('data-partial', name);
      this.$('[data-partial="' + name + '"]').replaceWith($el);
      return this;
    },

    render: function() {
      this.$el.html(maybeByName(this.jst)(_(this).result('data')));
      _(this.partials).keys().forEach(this.renderPartial, this);
      return this;
    }
  });

  _.extend(exports, {
    LabelView: LabelView,
    UniqueView: UniqueView,
    ConfirmView: ConfirmView,
    TemplateView: TemplateView,
    MessageTextView: MessageTextView
  });
})(go.components.views = {});
