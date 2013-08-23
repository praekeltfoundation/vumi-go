// go.components.actions
// =====================
// Reusable components for UI actions

(function(exports) {
  var Eventable = go.components.structures.Eventable;

  var PopoverView = go.components.views.PopoverView;

  var PopoverNotifierView = PopoverView.extend({
    templates: {
      busy: 'JST.components_notifiers_popover_busy',
      message: 'JST.components_notifiers_popover_message'
    },

    bootstrapOptions: function() {
      var options = {trigger: 'manual'};
      if (this.animate) { options.animation = true; }
      return options;
    },

    target: function() { return this.action.$el; },

    animate: true,
    delay: 400,

    messages: {
      success: function() { return this.action.name + ' successful!'; },
      error: function() { return this.action.name + ' failed :/'; },
    },

    initialize: function(options) {
      PopoverNotifierView.__super__.initialize.call(this, options);

      this.action = options.action;
      if ('delay' in options) { this.delay = options.delay; }
      if ('animate' in options) { this.animate = options.animate; }

      if (options.messages) {
        this.messages = _({}).defaults(
          options.messages,
          this.messages);
      }

      go.utils.bindEvents(this.bindings, this);
    },

    messageFor: function(eventName) {
      return go.utils.functor(this.messages[eventName]).call(this);
    },

    _delayedCall: function(fn) {
      if (this.delay > 0 && this.animate) {
        _.delay(fn.bind(this), this.delay);
      } else {
        fn.call(this);
      }
      return this;
    },

    blink: function(fn) {
      if (this.hidden) {
        fn.call(this);
        this.show();
      } else {
        this.hide();
        this._delayedCall(function() {
          fn.call(this);
          this.show();
        });
      }

      return this;
    },

    resetClassName: function(className) {
      this.popover
        .tip()
        .removeClass('error')
        .removeClass('success')
        .removeClass('info')
        .addClass('notifier')
        .addClass(className);

      return this;
    },

    renderMessage: function(type) {
      this.blink(function() {
        var jst = go.utils.maybeByName(this.templates.message);
        this.$el.html(jst({message: this.messageFor(type)}));
        this.resetClassName(type);
      });

      return this;
    },

    renderBusy: function() {
      this.blink(function() {
        var jst = go.utils.maybeByName(this.templates.busy);
        this.$el.html(jst());
        this.resetClassName('info');
      });
    },

    bindings: {
      'invoke action': function() {
        this.renderBusy();
      },

      'success action': function() {
        this.renderMessage('success');
      },

      'error action': function() {
        this.renderMessage('error');
      },
    },

    events: {
      'click .close': function(e) {
        e.preventDefault();
        this.hide();
      }
    }
  });

  var ActionView = Backbone.View.extend({
    name: 'Unnamed',

    useNotifier: false,
    notifierOptions: {type: PopoverNotifierView},

    constructor: function(options) {
      options = options || {};
      ActionView.__super__.constructor.call(this, options);

      this.name = options.name || this.name;

      if (options.notifier || options.useNotifier) { this.useNotifier = true; }
      this.initNotifier(options.notifier);
    },

    initNotifier: function(options) {
      if (!this.useNotifier) { return; }

      options = _(options || {}).defaults(
        this.notifierOptions,
        {action: this});

      this.notifier = new options.type(options);
    },

    invoke: function() {},

    events: {
      'click': function(e) {
        this.invoke();
        e.preventDefault();
      }
    },
  });

  // View for saving a model to the server side
  var SaveActionView = ActionView.extend({
    name: 'Save',

    initialize: function(options) {
      if (options.sessionId) { this.sessionId = options.sessionId; }
    },

    invoke: function() {
      var options = {
        success: function() { this.trigger('success'); }.bind(this),
        error: function() { this.trigger('error'); }.bind(this)
      };

      if (this.sessionId) { options.sessionId = this.sessionId; }
      this.model.save({}, options);
      this.trigger('invoke');

      return this;
    }
  });

  // View for resetting a model to its initial state
  var ResetActionView = ActionView.extend({
    name: 'Reset',

    initialize: function() {
      this.backup = this.model.toJSON();
    },

    invoke: function() {
      var self = this;
      this.trigger('invoke');

      _.defer(function() {
        self.model.set(self.backup);
        self.trigger('success');
      });

      return this;
    }
  });

  // View that invokes its action by sending an ajax request to the server side
  //
  // NOTE: Ideally, only our models should be interacting with the server side.
  // This view is a temporary solution, and should be replaced as soon as we
  // are in a position where the data on our pages can be managed by models
  // syncing with our api.
  var CallActionView = ActionView.extend({
    url: function() { return this.$el.attr('data-url'); },

    data: {},

    ajax: {},

    constructor: function(options) {
      CallActionView.__super__.constructor.call(this, options);

      if (options.url) { this.url = options.url; }
      if (options.data) { this.data = options.data; }
      if (options.ajax) { this.ajax = options.ajax; }
    },

    invoke: function() {
      var url = _(this).result('url');

      var ajax = _({
        type: 'post',
        data: _(this).result('data')
      }).extend(
        url ? {url: url} : {},
        _(this).result('ajax'));

      var success = ajax.success,
          error = ajax.error;

      ajax.success = function() {
        if (success) { success.apply(this, arguments); }
        this.trigger('success');
      }.bind(this);

      ajax.error = function() {
        if (error) { error.apply(this, arguments); }
        this.trigger('error');
      }.bind(this);

      $.ajax(ajax);
      this.trigger('invoke');

      return this;
    }
  });

  _(exports).extend({
    ActionView: ActionView,
    SaveActionView: SaveActionView,
    ResetActionView: ResetActionView,
    CallActionView: CallActionView,

    PopoverNotifierView: PopoverNotifierView
  });
})(go.components.actions = {});
