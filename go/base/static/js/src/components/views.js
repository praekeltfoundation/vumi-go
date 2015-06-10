// go.components.views
// ===================
// Generic, re-usable views for Go

(function(exports) {
  var utils = go.utils,
      functor = utils.functor,
      maybeByName = utils.maybeByName;

  var structures = go.components.structures,
      Extendable = structures.Extendable,
      ViewCollection = structures.ViewCollection;

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
      var text = this.$el.val();
      var non_ascii = go.utils.non_ascii(text);
      this.containsNonAscii = (non_ascii.length > 0);
      this.totalChars = text.length;
      this.totalBytes = text.length * (1 + this.containsNonAscii);
      this.totalSMS = Math.ceil(this.totalBytes / this.SMS_MAX_CHARS);
      var html;
      if (this.containsNonAscii) {
          html = [
              'Non-ASCII characters: ' + non_ascii.join(', '),
              this.totalChars + ' characters used (~' +
                  this.totalBytes + ' bytes)',
              this.totalSMS + ' smses',
          ].join("<br>");
          $p.addClass("text-danger");
      }
      else {
          html = [
              this.totalChars + ' characters used',
              this.totalSMS + ' smses',
          ].join("<br>");
          $p.removeClass("text-danger");
      }
      $p.html(html);
      return this;
    }
  });

  var ConfirmView = Backbone.View.extend({
    className: 'modal fade',

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

      this.on('ok', this.resetActionHandlers);
      this.on('cancel', this.resetActionHandlers);
    },

    animate: function(animated) {
      if (animated) { this.$el.addClass('fade'); }
      else { this.$el.removeClass('fade'); }
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

    remove: function() {
      this.off();
      return ConfirmView.__super__.remove.call(this);
    },

    render: function() {
      this.$el
        .appendTo($('body'))
        .html(maybeByName(this.template)({self: this}))
        .modal('show');

      this.delegateEvents();
      return this;
    }
  });

  var PopoverView = Backbone.View.extend({
    target: null,

    bootstrapOptions: {},

    constructor: function(options) {
      PopoverView.__super__.constructor.call(this, options);

      if (options.target) { this.target = options.target; }

      if (options.bootstrap) {
        this.bootstrapOptions = _({}).defaults(
          options.bootstrap,
          this.bootstrapOptions);
      }

      this.hidden = true;
      this.resetPopover();
      this.on('show', function() { this.delegateEvents(); });
    },

    remove: function() {
      PopoverView.__super__.remove.apply(this, arguments);
      if (this.popover) { this.popover.destroy(); }
    },

    resetPopover: function() {
      this.popover = _(this)
        .result('target')
        .popover(
          _({content: this.$el, html: true}).defaults(
          _(this).result('bootstrapOptions')))
        .data('bs.popover');

      return this;
    },

    show: function() {
      if (this.hidden) {
        this.render();
        this.resetPopover();
        this.popover.show();
        this.hidden = false;
        this.trigger('show');
      }

      return this;
    },

    hide: function() {
      if (!this.hidden) {
        this.popover.hide();
        this.hidden = true;
        this.trigger('hide');
      }

      return this;
    },

    toggle: function() {
      return this.hidden
        ? this.show()
        : this.hide();
    }
  });

  var Partials = Extendable.extend({
    constructor: function(items) {
      this.items = {};
      _(items).each(this.add, this);
    },

    _ensureArray: function(obj) {
      if (obj instanceof ViewCollection) { return obj.values(); }

      return _.isArray(obj)
        ? obj
        : [obj];
    },

    add: function(partial, name) {
      this.items[name] = this._ensureArray(partial);
      return this;
    },

    toPlaceholders: function() {
      var placeholders = {};

      _(this.items).each(function(partial, name) {
        var placeholder = placeholders[name] = [];

        return partial.forEach(function(p, i) {
          placeholder.push('<div '
            + 'data-partial="' + name + '" '
            + 'data-partial-index="' + i + '"'
            + "></div>");
        });
      });

      return placeholders;
    },

    applyPartial: function(p, $at, data) {
      if (p instanceof Backbone.View) {
        p.render();
        $at.replaceWith(p.$el);
        p.delegateEvents();
      } else {
        p = $(maybeByName(p)(data));
        $at.replaceWith(p);
      }

      return this;
    },

    applyTo: function(target, data) {
      var self = this;
      data = data || {};

      _(this.items).each(function(partial, name) {
        target.find('[data-partial="' + name + '"]').each(function() {
          var $at = $(this),
              i = $at.attr('data-partial-index');

          self.applyPartial(partial[i], $at, data);
        });
      });

      return this;
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

    render: function() {
      var partials = new Partials(this.partials),
          data = _(this).result('data');

      data.partials = partials.toPlaceholders();
      this.$el.html(maybeByName(this.jst)(data));

      partials.applyTo(this.$el, data);
      return this;
    }
  });

  _.extend(exports, {
    UniqueView: UniqueView,
    ConfirmView: ConfirmView,
    PopoverView: PopoverView,
    Partials: Partials, 
    TemplateView: TemplateView,
    MessageTextView: MessageTextView
  });
})(go.components.views = {});
