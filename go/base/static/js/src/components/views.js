// go.components.views
// ===================
// Generic, re-usable views for Go

(function(exports) {
  var utils = go.utils,
      functor = utils.functor,
      maybeByName = utils.maybeByName;

  var ViewCollection = go.components.structures.ViewCollection;

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

  var PopoverView = Backbone.View.extend({
    target: null,

    popoverOptions: {},

    initialize: function(options) {
      if (options.target) { this.target = options.target; }
      if (options.popover) { this.popoverOptions = options.popover; }

      this.popover = null;
      this.hidden = true;
    },

    remove: function() {
      PopoverView.__super__.remove.apply(this, arguments);
      if (this.popover) { this.popover.destroy(); }
    },

    show: function() {
      this.render();

      this.popover = _(this)
        .result('target')
        .popover(
          _({content: this.$el, html: true}).defaults(
          _(this).result('popoverOptions')))
        .data('popover');

      this.popover.show();
      this.hidden = false;
      return this;
    },

    hide: function() {
      if (this.popover) {
        this.popover.hide();
        this.hidden = true;
      }
      return this;
    },

    toggle: function() {
      return this.hidden
        ? this.show()
        : this.hide();
    }
  });

  var TemplateView = Backbone.View.extend({
    jst: null,

    partials: {},

    data: {},

    initialize: function(options) {
      if (options.data) { this.data = options.data; }
      if (options.jst) { this.jst = options.jst; }
      this.partials = _({}).extend(this.partials, options.partials || {});
    },

    insertPartial: function($p, $at, name) {
      $at.replaceWith($p);
      $p.attr('data-partial', name);
      return this;
    },

    renderPartial: function(p, $at, name) {
      if (p instanceof Backbone.View) {
        p.render();
        this.insertPartial(p.$el, $at, name);
        p.delegateEvents();
      } else {
        p = $(maybeByName(p)(_(this).result('data')));
        this.insertPartial(p, $at, name);
      }

      return this;
    },

    renderPartials: function(name) {
      var partials = this.partials[name],
          $placeholders = this.$('[data-partial="' + name + '"]');

      if (partials instanceof ViewCollection) { partials = partials.values(); }
      else if (!_.isArray(partials)) { partials = [partials]; }

      partials.forEach(function(p, i) {
        this.renderPartial(p, $placeholders.eq(i), name);
      }, this);

      return this;
    },

    render: function() {
      this.$el.html(maybeByName(this.jst)(_(this).result('data')));
      _(this.partials).keys().forEach(this.renderPartials, this);
      return this;
    }
  });

  _.extend(exports, {
    UniqueView: UniqueView,
    ConfirmView: ConfirmView,
    PopoverView: PopoverView,
    TemplateView: TemplateView,
    MessageTextView: MessageTextView
  });
})(go.components.views = {});
