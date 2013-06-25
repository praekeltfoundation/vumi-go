// go.components.grid
// ==================
// Components for self-maintaining grids of items.

(function(exports) {
  var utils = go.utils,
      idOfView = utils.idOfView;

  var views = go.components.views,
      UniqueView = views.UniqueView;

  var structures = go.components.structures,
      ViewCollection = structures.ViewCollection;

  var RowItemView = UniqueView.extend({
    span: 3,

    uuid: function() { return idOfView(this.item); },

    initialize: function(options) {
      this.item = options.item;
      this.span = this.spanOfEl(this.item.$el) || options.span || this.span;
      this.$el.addClass('span' + this.span);
    },

    spanOfEl: function($el) {
      var classes = ($el.attr('class') || '').split(' '),
          i = classes.length;

      while (i--) {
        var c = classes[i];
        if (c.substr(0, 4) === 'span') { return parseInt(c.slice(4), 10); }
      }

      return null;
    },

    render: function() {
      this.$el.append(this.item.$el);
      this.item.render();
      return this;
    }
  });

  var RowView = UniqueView.extend({
    className: 'row',

    initialize: function(options) {
      this.spanSum = 0;
      this.items = [];
    },

    add: function(item) {
      this.items.push(item);
      this.spanSum += item.span;
      return this;
    },

    render: function() {
      this.items.forEach(function(item) {
        this.$el.append(item.$el);
        item.render();
      }, this);

      return this;
    }
  });

  var RowCollection = ViewCollection.extend({
    addDefaults: _({
      render: false
    }).defaults(ViewCollection.prototype.addDefaults),

    type: RowView,
    rowItemType: RowItemView,

    maxSpan: 12,

    initialize: function(options) {
      this.rowItemType = options.rowItemType || this.rowItemType;
      this._ensureArray(options.items).forEach(this.addItem, this);
    },

    _ensureArray: function(obj) {
      return obj instanceof ViewCollection
        ? obj.values()
        : obj;
    },

    viewOptions: function() { return {uuid: 'row' + this.size()}; },

    addItem: function(item) {
      var row = this.last() || this.add(),
          rowItem = new this.rowItemType({item: item});

      if (row.spanSum + rowItem.span > this.maxSpan) { row = this.add(); }

      row.add(rowItem);
      return this;
    }
  });

  // A self-maintaining grid of items.
  //
  // Options:
  //   - items: A collection of views to be maintained in the grid
  var GridView = Backbone.View.extend({
    className: 'container',

    rowType: RowView,
    rowItemType: RowItemView,
    rowCollectionType: RowCollection,

    initialize: function(options) {
      this.items = this._ensureViewCollection(options.items);
      this.resetRows();

      this.items.on('add', this.render, this);
      this.items.on('remove', this.render, this);
    },

    _ensureViewCollection: function(obj) {
      return obj instanceof ViewCollection
        ? obj
        : new ViewCollection({views: obj});
    },

    resetRows: function() {
      this.rows = new this.rowCollectionType({
        items: this.items,
        type: this.rowType,
        rowItemType: this.rowItemType
      });
      return this;
    },

    render: function() {
      this.resetRows();

      this.$el.empty();
      this.rows.render();
      this.rows.each(function(r) { this.$el.append(r.$el); }, this);

      return this;
    }
  });

  _.extend(exports, {
    RowView: RowView,
    RowItemView: RowItemView,
    RowCollection: RowCollection,
    GridView: GridView
  });
})(go.components.grid = {});
