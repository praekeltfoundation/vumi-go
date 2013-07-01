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

    className: 'item',

    initialize: function(options) {
      this.item = options.item;

      this.span = this.spanOfEl(this.item.$el) || options.span || this.span;
      this.$el.addClass('span' + this.span);
      if (options.extraClass) { this.$el.addClass(options.extraClass); }

      var itemId = idOfView(this.item);
      this.uuid = 'item:' + itemId;
      this.$el.data('item-id', itemId);
    },

    _spanRe: /span[0-9]/g,

    spanOfEl: function($el) {
      var classes = ($el.attr('class') || '').match(this._spanRe);

      if (classes && classes.length === 1) {
        var span = parseInt(classes[0].slice(4), 10);
        if (!isNaN(span)) { return span; }
      }

      return null;
    },

    render: function() {
      this.$el.append(this.item.$el);
      this.item.render();
      return this;
    }
  });

  var RowView = Backbone.View.extend({
    className: 'row',

    initialize: function(options) {
      options = options || {};
      if (options.extraClass) { this.$el.addClass(options.extraClass); }

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
      render: false,
      addModel: false
    }).defaults(ViewCollection.prototype.addDefaults),

    type: RowView,
    rowItemType: RowItemView,

    maxSpan: 12,

    initialize: function(options) {
      this.rowClass = options.rowClass;
      this.itemClass = options.itemClass;
      this.itemSpan = options.itemSpan;

      this.rowItemType = options.rowItemType || this.rowItemType;
      this._ensureArray(options.items).forEach(this.addItem, this);
    },

    _ensureArray: function(obj) {
      return obj instanceof ViewCollection
        ? obj.values()
        : obj;
    },

    viewOptions: function() {
      return {
        id: 'row' + this.size(),
        extraClass: this.rowClass
      };
    },

    addItem: function(item) {
      var row = this.last() || this.add();

      var rowItem = new this.rowItemType({
        item: item,
        span: this.itemSpan,
        extraClass: this.itemClass
      });

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
    className: 'grid container',

    rowType: RowView,
    rowItemType: RowItemView,
    rowCollectionType: RowCollection,

    sortableOptions: {},

    initialize: function(options) {
      this.items = this._ensureViewCollection(options.items);
      this.sortableOptions = options.sortableOptions || this.sortableOptions;

      if (options.gridClass) { this.$el.addClass(options.gridClass); }

      this.rowClass = options.rowClass;
      this.itemClass = options.itemClass;
      this.itemSpan = options.itemSpan;

      this.rowType = options.rowType || this.rowType;
      this.rowItemType = options.rowItemType || this.rowItemType;
      this.rowCollectionType = options.rowCollectionType
                            || this.rowCollectionType;

      this.items.on('add', this.render, this);
      this.items.on('remove', this.render, this);

      this.resetRows();
    },

    _ensureViewCollection: function(obj) {
      return obj instanceof ViewCollection
        ? obj
        : new ViewCollection({
          orderable: true,
          arrangeable: true,
          views: obj
        });
    },

    resetRows: function() {
      this.rows = new this.rowCollectionType({
        items: this.items,
        type: this.rowType,
        rowItemType: this.rowItemType,
        rowClass: this.rowClass,
        itemSpan: this.itemSpan,
        itemClass: this.itemClass
      });
      return this;
    },

    itemOrder: function() {
      return this.$('.row').map(function() {
        return $(this)
          .find('.item')
          .map(function() { return $(this).data('item-id'); }).get();
      }).get();
    },

    // NOTE: The grid relies on the items collection to rearrange its items
    // correctly. The grid shouldn't know (or be responsible for) how item and
    // model ordering happens. If this isn't handled correctly, the ui ordering
    // will be lost.
    reorder: function() {
      this.items.rearrange(this.itemOrder());
      this.render();
    },

    _sortableOptions: function() {
      var opts = _(this).result('sortableOptions');

      return _({}).extend(opts, {
        connectWith: '.row',
        stop: function(e, ui) {
          this.reorder();
          if (opts.stop) { opts.stop(e, ui); }
        }.bind(this)
      });
    },

    render: function() {
      this.rows.each(function(r) { r.$el.detach(); });
      this.resetRows();

      this.rows.each(function(r) { this.$el.append(r.$el); }, this);
      this.rows.render();

      this.$('.row').sortable(this._sortableOptions());

      this.trigger('render');
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
