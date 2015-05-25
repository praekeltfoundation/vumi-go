// go.components.actions
// =====================
// Reusable components for UI actions

(function(exports) {
  var Eventable = go.components.structures.Eventable;

  var PopoverView = go.components.views.PopoverView;

  var capitalise = go.utils.capitalise,
      delayed = go.utils.delayed,
      functor = go.utils.functor,
      bindEvents = go.utils.bindEvents,
      maybeByName = go.utils.maybeByName;

  var PopoverNotifierView = PopoverView.extend({
    templates: {
      busy: 'JST.components_notifiers_popover_busy',
      message: 'JST.components_notifiers_popover_message'
    },

    bootstrapOptions: function() {
      var options = {
        trigger: 'manual',
        placement: 'top',
        container: 'body'
      };

      if (this.animate) { options.animation = true; }
      return options;
    },

    target: function() { return this.action.$el; },

    animate: true,
    busyWait: 400,
    delay: 400,

    messages: {
      success: function() {
        return capitalise(_(this.action).result('name')) + ' successful.';
      },
      error: function() {
        return capitalise(_(this.action).result('name')) + ' failed.';
      },
    },

    initialize: function(options) {
      PopoverNotifierView.__super__.initialize.call(this, options);

      this.action = options.action;
      if ('delay' in options) { this.delay = options.delay; }
      if ('animate' in options) { this.animate = options.animate; }
      if ('busyWait' in options) { this.busyWait = options.busyWait; }

      if (options.messages) {
        this.messages = _({}).defaults(
          options.messages,
          this.messages);
      }

      bindEvents(this.bindings, this);
    },

    messageFor: function(eventName) {
      return functor(this.messages[eventName]).call(this);
    },

    blink: function(fn) {
      if (this.hidden) {
        fn.call(this);
        this.show();
      } else {
        this.hide();
        delayed(function() {
          fn.call(this);
          this.show();
        }, this.delay, this);
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
        var jst = maybeByName(this.templates.message);
        this.$el.html(jst({message: this.messageFor(type)}));
        this.resetClassName(type);
      });

      return this;
    },

    renderBusy: function() {
      var done = false,
          self = this;

      this.listenToOnce(this.action, 'success', function() { done = true; });
      this.listenToOnce(this.action, 'error', function() { done = true; });

      // Only show the 'busy' notification if we are waiting long enough
      delayed(function() {
        if (done) { return; }

        self.blink(function() {
          var jst = maybeByName(self.templates.busy);
          self.$el.html(jst());
          self.resetClassName('info');
        });
      }, this.busyWait);

      return this;
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
    async: true,

    initialize: function(options) {
      this.backup = this.model.toJSON();
      if ('async' in options) { this.async = options.async; }
    },

    _deferredCall: function(fn) {
      if (this.async) { _.defer(fn.bind(this)); }
      else fn.call(this);
      return this;
    },

    invoke: function() {
      this.trigger('invoke');

      this._deferredCall(function() {
        this.model.set(this.backup);
        this.trigger('success');
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
