// go.components.templating
// =========================
// Components the client-side templates used in Go.

(function(exports) {
  var maybeByName = go.utils.maybeByName;

  var Template = Backbone.View.extend({
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
      this.$el.html(this.jst(_(this).result('data')));
      _(this.partials).keys().forEach(this.renderPartial, this);
      return this;
    }
  });

  _.extend(exports, {
    Template: Template
  });
})(go.components.templating = {});
