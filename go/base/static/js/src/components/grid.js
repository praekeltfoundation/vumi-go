// go.components.grid
// ==================
// Components for self-maintaining grids of items.

(function(exports) {
  var Lookup = go.components.structures.Lookup;

  var GridItems = Lookup.extend({
    ordered: true,
    comparator: function($el) { return $el.data('grid:index'); },

    arrangeable: true,
    arranger: function($el, i) { $el.data('grid:index', i); }
  });

  // A self-maintaining grid of items.
  //
  // Options:
  //   - items: A collection of views to be maintained in the grid
  var GridView = Backbone.View.extend({
    className: 'container',
    rowClassName: 'row',

    sortableOptions: {},

    initialize: function(options) {
      this.items = new GridItems();
      this.width = options.width || this.$el.outerWidth();

      if (options.rowClassName) { this.rowClassName = options.rowClassName; }
      if (options.sortable) { this.sortableOptions = options.sortable; }
    },

    $rows: function() { return this.$('.' + this.rowClassName); },

    _ensureEl: function(viewOrEl) {
      return viewOrEl instanceof Backbone.View
        ? viewOrEl.$el
        : $(viewOrEl);
    },

    add: function(key, item, options) {
      options = options || {};
      item = this._ensureEl(item);

      item.data({
        'grid:key': key,
        'grid:index': options.index || this.items.size()
      });

      this.items.add(key, item, options);
      return this;
    },

    remove: function(key, options) {
      return this.items.remove(key, options);
    },

    clear: function() {
      this.items = new GridItems();
      return this;
    },

    _reorder: function() {
      var newOrder = this.$rows()
        .children()
        .map(function() { return $(this).data('grid:key'); })
        .get();

      this.items.rearrange(newOrder);
      this.trigger('reorder', this.items.keys());
      return this;
    },

    _sortableOptions: function() {
      var opts = _(this).result('sortableOptions');

      return _({}).extend(opts, {
        connectWith: '.' + this.rowClassName,
        stop: function(e, ui) {
          this._reorder();
          this.render();
          if (opts.stop) { opts.stop(e, ui); }
        }.bind(this)
      });
    },

    _newRow: function() {
      this._$lastRow = $('<div>').addClass(this.rowClassName);
      this._remainingWidth = this.width;
      this.$el.append(this._$lastRow);
      return this;
    },

    _append: function(item) {
      var itemWidth = item.outerWidth();

      if (this._remainingWidth < itemWidth) { this._newRow(); }
      this._remainingWidth -= itemWidth;

      this._$lastRow.append(item);
      return this;
    },

    render: function() {
      var $oldRows = this.$rows();

      this._newRow();
      this.items.each(this._append, this);

      $oldRows.remove();
      this.$rows().sortable(this._sortableOptions());
      return this;
    }
  });

  _.extend(exports, {
    GridItems: GridItems,
    GridView: GridView
  });
})(go.components.grid = {});
