(function(exports) {
  var Grid = go.components.grid.Grid;


  var DialogueStateLayout = Backbone.View.extend({
    initialize: function(options) {
      options = _.defaults(options, {numCols: 3});

      this.states = options.states;
      this.numCols = options.numCols;
      this.colWidth = options.colWidth;
      this.setElement(this.states.view.$el);
      this.grid = new Grid({numCols: this.numCols});
    },

    render: function() {
      this.states.each(this.renderState, this);
    },

    renderState: function(state) {
      var layout = this.ensureLayout(state);
      state.$el.offset(this.offsetOf(layout.coords()));
    },

    offsetOf: function(coords) {
      var offset = this.$el.offset();

      return {
        left: offset.left + coords.x,
        top: offset.top + coords.y
      };
    },

    ensureLayout: function(state) {
      if (!state.model.has('layout')) this.initLayout(state);
      return state.model.get('layout');
    },

    initLayout: function(state) {
      var marginLeft = parseInt(state.$el.css('marginLeft'));
      var marginTop = parseInt(state.$el.css('marginTop'));

      var cell = this.grid.add({
        width: state.$el.outerWidth(true) - marginLeft,
        height: state.$el.outerHeight(true) - marginTop
      });

      state.model.set('layout', {
        x: cell.x + marginLeft,
        y: cell.y + marginTop
      }, {silent: true});
    }

  });


  exports.DialogueStateLayout = DialogueStateLayout;
})(go.apps.dialogue.layout = {});
