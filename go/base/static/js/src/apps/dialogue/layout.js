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

      this.onDrag = this.onDrag.bind(this);
      go.utils.bindEvents(this.bindings, this);
    },

    events: {
      'dblclick': function(e) {
        this.addAtEvent(e);
      }
    },

    render: function() {
      this.states.each(this.renderState, this);
    },

    offsetOf: function(coords) {
      var offset = this.$el.offset();

      return {
        left: offset.left + coords.x,
        top: offset.top + coords.y
      };
    },

    coordsOf: function(state) {
      var offset = this.$el.offset();
      var elOffset = state.$el.offset();

      return {
        x: elOffset.left - offset.left,
        y: elOffset.top - offset.top
      };
    },

    dragMargin: function() {
      // give an extra screen size's space so that users don't need to see the
      // bottom of the page grow
      return $(window).height();
    },

    addAtEvent: function(e) {
      var state = this.states.add();
      var offset = this.$el.offset();

      state.model.set('layout', {
        x: e.pageX - offset.left,
        y: e.pageY - offset.top
      });

      this.renderState(state);
      return state;
    },

    repaint: function() {
      // TODO only repaint the relevant connections
      jsPlumb.repaintEverything();
      this.trigger('repaint');
    },

    resizeToFit: function(state) {
      var height = this.$el.height();
      this.$el.height(Math.max(height, this.maxYOf(state)));
    },

    maxYOf: function(state) {
      var top = state.$el.position().top;
      var height = state.$el.outerHeight(true);
      return top + height + this.dragMargin();
    },

    renderState: function(state) {
      state.$el.draggable({
        drag: this.onDrag,
        handle: '.titlebar',
        containment: 'parent'
      });

      var layout = this.ensureLayout(state);
      state.$el.offset(this.offsetOf(layout.coords()));
      this.resizeToFit(state);
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
      });
    },

    onDrag: function(e) {
      var state = this.states.get($(e.target).attr('data-uuid'));

      state.model
        .get('layout')
        .set(this.coordsOf(state), {silent: true});

      this.repaint();
      this.resizeToFit(state);
    }
  });


  exports.DialogueStateLayout = DialogueStateLayout;
})(go.apps.dialogue.layout = {});
