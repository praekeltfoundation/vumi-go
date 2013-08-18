// go.router.show
// ==============

(function(exports) {
  var RouterActionView = go.router.views.RouterActionView;

  var RouterActionsView = Backbone.View.extend({
    initialize: function(options) {
      this.actions = this.$('.action').map(function() {
        return new RouterActionView({
          el: $(this),
          csrfToken: options.csrfToken
        });
      }).get();
    }
  });

  _.extend(exports, {
    RouterActionsView: RouterActionsView
  });
})(go.router.show = {});
