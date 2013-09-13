// go.router.views
// ===============

(function(exports) {
  var CallActionView = go.components.actions.CallActionView;

  // NOTE: This view will hopefully not be around too long. Ideally, we want
  // models and collections for our routers that can invoke their actions,
  // and make api requests accordingly.
  var RouterActionView = CallActionView.extend({
    name: function() { return this.$el.attr('data-action'); },
    data: function() { return {csrfmiddlewaretoken: $.cookie('csrftoken')}; },
    useNotifier: true,

    initialize: function(options) {
      this.on('success', function() { location.reload(); });
    },

    invoke: function() {
      var invoke = RouterActionView.__super__.invoke.bind(this);

      bootbox.confirm(
        'Are you sure you want to ' + this.name() + ' this router?',
        function(submit) { if (submit) { invoke(); } });
    }
  });

  _(exports).extend({
    RouterActionView: RouterActionView
  });
})(go.router.views = {});
