// go.components.actions
// =====================
// Reusable components for UI actions

(function(exports) {
  var ActionView = Backbone.View.extend({
    events: {
      'click': function(e) {
        this.invoke();
        e.preventDefault();
      }
    },

    invoke: function() {}
  });

  // View for saving a model to the server side
  var SaveView = ActionView.extend();

  // View for resetting a model to its initial state
  var ResetView = ActionView.extend();

  // View that invokes its action by sending an ajax request to the server side
  var CallActionView = ActionView.extend({
    url: function() { return this.$el.attr('data-url'); },

    data: function() {
      return {
        id:  this.$el.attr('data-id'),
        action: this.$el.attr('data-action')
      };
    },

    ajax: {},

    constructor: function(options) {
      options = options || {};
      CallActionView.__super__.constructor.call(this, options);

      if (options.url) { this.url = options.url; }
      if (options.data) { this.data = options.data; }
      if (options.ajax) { this.ajax = options.ajax; }
    },

    invoke: function() {
      var url = _(this).result('url');

      var ajax = _({
        type: 'post',
        dataType: 'JSON',
        contentType: 'application/json; charset=utf-8',
        data: JSON.stringify(_(this).result('data'))
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
    }
  });

  _(exports).extend({
    ActionView: ActionView,
    SaveView: SaveView,
    ResetView: ResetView,
    CallActionView: CallActionView
  });
})(go.components.actions = {});
