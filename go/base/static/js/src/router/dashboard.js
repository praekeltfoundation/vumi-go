// go.router.dashboard
// ===================

(function(exports) {
  var TableFormView = go.components.tables.TableFormView,
      RouterActionView = go.router.views.RouterActionView;

  var RouterDashboardView = TableFormView.extend({
    initialize: function(options) {
      RouterDashboardView.__super__.initialize.call(this, options);

      this.actions = this.$('.action').map(function() {
        return new RouterActionView({
          el: $(this),
          csrfToken: options.csrfToken
        });
      }).get();
    }
  });

  _.extend(exports, {
    RouterDashboardView: RouterDashboardView
  });
})(go.router.dashboard = {});
