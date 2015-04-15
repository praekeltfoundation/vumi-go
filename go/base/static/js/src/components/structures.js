// go.components.structures
// ========================
// Reusable, generic structures for Go

(function(exports) {
  var utils = go.utils,
      merge = utils.merge,
      maybeByName = utils.maybeByName,
      idOfModel = utils.idOfModel,
      idOfView = utils.idOfView;

  // Acts as a 'base' for class-like objects which can be extended (with the
  // prototype chain set up automatically)
  var Extendable = function () {};

  Extendable.extend = function() {
    // Backbone has an internal `extend()` function which it assigns to its
    // structures. We need this function, so we arbitrarily choose
    // `Backbone.Model`, since it has the function we are looking for.
    return Backbone.Model.extend.call(this, merge.apply(this, arguments));
  };

  // A class-like object onto which events can be bound and emitted
  var Eventable = Extendable.extend(Backbone.Events);

  var nativeSort = function(list, comparator, that) {
    return list.sort(comparator.bind(that || this));
  };

  // A structure that stores key-value pairs, provides helpful operations for
  // accessing the data, and emits events when items are added or removed.
  // Similar to a Backbone Collection, except the contents are key-value pairs
  // instead of models.
  //
  // Arguments:
  //   - items: the initial objects to be added
  //
  // Events emitted:
  //   - 'add' (key, value) - Emitted when an item is added
  //   - 'remove' (key, value) - Emitted when an item is removed
  var Lookup = Eventable.extend({
    addDefaults: {silent: false, sort: true},
    removeDefaults: {silent: false, sort: true},

    ordered: false,  // whether the lookup's items have an ordering
    comparator: function(v) { return v.ordinal || 0; },

    arrangeable: false, // whether the lookup's items can be reordered
    arranger: function(v, ordinal) { v.ordinal = ordinal; },

    constructor: function(items, options) {
      options = options || {};
      this.ordered = options.ordered || this.ordered;
      this.comparator = options.comparator || this.comparator;
      this.arrangeable = options.ordered || this.arrangeable;
      this.arranger = options.arranger || this.arranger;

      this._items = {};
      this._itemList = [];

      for (var k in (items || {})) {
        this.add(k, items[k], {silent: true, sort: false});
      }

      if (this.ordered) {
        this._initSorting();
        this.sort();
      }
    },

    _initSorting: function() {
      if (_.isString(this.comparator)) {
        this._sorter = _.sortBy;
        this._comparator = this.comparators.string;
      } else if (this.comparator.length === 1) {
        this._sorter = _.sortBy;
        this._comparator = this.comparators.iterator;
      } else {
        this._sorter = nativeSort;
        this._comparator = this.comparators.native;
      }
    },

    comparators: {
      string: function(item) {
        return item.value[this.comparator];
      },

      iterator: function(item) {
        return this.comparator(item.value);
      },

      native: function(item1, item2) {
        return this.comparator(item1.value, item2.value);
      },
    },

    size: function() { return this._itemList.length; },

    keys: function() { return _(this._itemList).pluck('key'); },

    values: function() { return _(this._itemList).pluck('value'); },

    items: function() { return _.clone(this._items); },

    each: function(fn, that) { return this.values().forEach(fn, that); },

    map: function(fn, that) { return this.values().map(fn, that); },

    where: function(props) { return _.where(this.values(), props); },

    findWhere: function(props) { return _.findWhere(this.values(), props); },

    callAt: function(i, fn, that) {
      var item = this._itemList[i];
      fn.call(that, item.key, item.value, i);
    },

    eachItem: function(fn, that) {
      var i = -1,
          n = this.size();

      while (++i < n) { this.callAt(i, fn, that); }
    },

    has: function(k) { return _.has(this._items, k); },

    get: function(key) { return this._items[key]; },

    at: function(i) {
      var item = this._itemList[i];
      return item ? item.value : undefined;
    },

    keyAt: function(i) {
      var item = this._itemList[i];
      return item ? item.key : undefined;
    },

    _indexOf: function(propName, value) {
      var i = this.size(),
          items = this._itemList,
          item;

      while (i--) {
        item = items[i];
        if (item && item[propName] === value) { return i; }
      }

      return -1;
    },

    indexOf: function(v) { return this._indexOf('value', v); },

    indexOfKey: function(k) { return this._indexOf('key', k); },

    last: function() { return this.at(this.size() - 1); },

    lastKey: function() { return this.keyAt(this.size() - 1); },

    add: function(key, value, options) {
      options = _(options || {}).defaults(this.addDefaults);

      this._items[key] = value;
      this._itemList.push({key: key, value: value});

      if (options.sort) { this.sort(); }
      if (!options.silent) { this.trigger('add', key, value); }

      return this;
    },

    remove: function(key, options) {
      options = _(options || {}).defaults(this.removeDefaults);

      var value = this._items[key];
      if (value) {
        this._itemList.splice(this.indexOf(value), 1);
        delete this._items[key];

        if (!options.silent) { this.trigger('remove', key, value); }
      }
      return value;
    },

    sort: function() {
      if (this.ordered) {
        this._itemList = this._sorter(this._itemList, this._comparator, this);
        this.trigger('sort');
      }
      return this;
    },

    rearrange: function(keys) {
      if (this.ordered && this.arrangeable) {
        keys.forEach(function(k, i) { this.arranger(this.get(k), i); }, this);
        this.sort();
      }
    }
  });

  // A self-maintained, 'flattened' collection of all the items of lookups
  // subscribed to it.
  //
  // Arguments:
  //   - lookups: key-lookup pairs for the initial members to subscribe.
  //
  // Events emitted:
  //   - 'add' (key, value) - Emitted when an item is added
  //   - 'remove' (key, value) - Emitted when an item is removed
  var LookupGroup = Lookup.extend({
    constructor: function(lookups, options) {
      Lookup.prototype.constructor.call(this, {}, options);
      this.members = new Lookup();

      // Lookup of item owners by item keys
      this._owners = {};

      lookups = lookups || {};
      for (var k in lookups) { this.subscribe(k, lookups[k]); }
    },

    ownerOf: function(key) { return this._owners[key]; },

    onMemberAdd: function(member, key, value, options) {
      this._owners[key] = member;
      return Lookup.prototype.add.call(this, key, value, options);
    },

    onMemberRemove: function(key, options) {
      delete this._owners[key];
      return Lookup.prototype.remove.call(this, key, options);
    },

    add: function(memberKey, key, value, options) {
      var member = this.members.get(memberKey);
      member.add(key, value, options);
      return this;
    },

    remove: function(key, options) {
      var member = this.ownerOf(key);
      return member.remove(key, options);
    },

    subscribe: function(key, lookup) {
      var add = _(this.onMemberAdd).bind(this, lookup);
      lookup.eachItem(add);

      this.listenTo(lookup, 'add', add);
      this.listenTo(lookup, 'remove', this.onMemberRemove, this);

      this.members.add(key, lookup);
      return this;
    },

    unsubscribe: function(key) {
      var lookup = this.members.get(key);
      this.stopListening(lookup);

      lookup.keys().forEach(this.onMemberRemove, this);
      this.members.remove(key);
      return lookup;
    }
  });

  // Maintains a collection of views, allowing views to be created dynamically
  // and interacted with collectively.
  //
  // Optionally accepts a collection of models, maintaining a corresponding
  // collection of views. New views are created when models are added to the
  // collection, old views are removed when models are removed from the
  // collection.
  //
  // Options:
  // - [views]: A list of views or view options for the initial views to add
  // - [models]: A collection of models to create views for. Does not need to
  // correspond with the initial views.
  // - [type]: The view type to instantiate for each new view.
  //
  // Events emitted:
  //   - 'add' (id, view) - Emitted when a view is added
  //   - 'remove' (id, view) - Emitted when a view is removed
  var ViewCollection = Lookup.extend({
    type: Backbone.View,

    // The model attribute representing a model subtype. Used to create a
    // view subtype instance corresponding to the model subtype instance
    typeAttr: 'type',

    // The default options passed to each new view
    viewOptions: {},

    // The default attributes for each new view's model
    modelDefaults: {},

    addDefaults: _({
      render: true,  // render view after adding
      addModel: true  // add the model if it is not in the collection
    }).defaults(Lookup.prototype.addDefaults),

    removeDefaults: _({
      render: true,  // render view after adding
      removeModel: true  // remove the model if it is in the collection
    }).defaults(Lookup.prototype.removeDefaults),

    constructor: function(options) {
      Lookup.prototype.constructor.call(this, {}, options);

      this._byModelId = {};
      this.models = this._ensureCollection(options.models);

      this.addLock = false;
      this.removeLock = false;
      this.listenTo(this.models, 'add', this.onModelAdd);
      this.listenTo(this.models, 'remove', this.onModelRemove);

      this.type = options.type || this.type;
      this.typeAttr = this.type.prototype.typeAttr || this.typeAttr;

      this.initialize(options);

      this.models.each(function(m) {
        this.add(
          {model: m},
          {render: false, silent: true});
      }, this);

      (options.views || []).forEach(function(v) {
        this.add(v, {render: false, silent: true});
      }, this);
    },

    initialize: function() {},

    idOfModel: idOfModel,
    idOfView: idOfView,

    // Useful in situations where we need to do something with a view in the
    // collection, but aren't sure whether we were given the view or its id.
    resolveView: function(viewOrId) {
      return this.get(this.idOfView(viewOrId));
    },

    _ensureModel: function(obj) {
      if (obj instanceof Backbone.Model) { return obj; }

      var modelType = this.models.model,
          attrs = _(obj || {}).defaults(_(this).result('modelDefaults'));

      return modelType.build
        ? modelType.build(attrs)
        : new modelType(attrs);
    },

    _ensureCollection: function(obj) {
      if (obj instanceof Backbone.Collection) { return obj; }
      if (obj instanceof Backbone.Model) { obj = [obj]; }
      return new Backbone.Collection(_.isArray(obj) ? obj : []);
    },

    _ensureView: function(obj) {
      return obj instanceof Backbone.View
        ? obj
        : this.create(obj);
    },

    onModelAdd: function(model) {
      // Don't try add the view if we added the model
      if (this.addLock) { this.addLock = false; }
      else { this.add({model: model}); }
    },

    onModelRemove: function(model) {
      // Don't try remove the view if we are removed the model
      if (this.removeLock) { this.removeLock = false; }
      else { this.removeByModel(model); }
    },

    determineType: function(options) {
      var type = this.type,
          subtypes = type.prototype.subtypes;

      if (!options.model || !subtypes) { return type; }

      var typeName = options.model.get(this.typeAttr);
      return !typeName
        ? type
        : maybeByName(subtypes[typeName]) || type;
    },

    // Override to specialise how each view is created
    create: function(options) {
      options = _(options || {}).defaults(_(this).result('viewOptions'));
      var type = this.determineType(options);
      return new type(options);
    },

    add: function(view, options) {
      view = view || {};
      options = _(options || {}).defaults(this.addDefaults);

      var model = view.model;
      if (model || options.addModel) {
        view.model = model = this._ensureModel(model);

        if (options.addModel && !this.models.get(model)) {
          if (!options.silent) { this.addLock = true; }
          this.models.add(model, {silent: options.silent});
        }
      }

      view = this._ensureView(view);
      if (model) { this._byModelId[this.idOfModel(model)] = view; }
      Lookup.prototype.add.call(this, this.idOfView(view), view, options);

      if (options.render) { this.ordered ? this.render() : view.render(); }
      return view;
    },

    remove: function(viewOrId, options) {
      options = _(options || {}).defaults(this.removeDefaults);

      var id = this.idOfView(viewOrId),
          view = this.get(id);

      if (!view) { return; }
      if (typeof view.destroy === 'function') { view.destroy(options); }

      var model = view.model;
      if (model && this.models.get(model)) {
        delete this._byModelId[this.idOfModel(model)];

        if (options.removeModel) {
          if (!options.silent) { this.removeLock = true; }
          this.models.remove(model, {silent: options.silent});

          // Ensure the model is removed from the store so it won't cause
          // duplication errors if a new model with the same id is added to the
          // store (backbone-relational does not appear to do this
          // automatically)
          Backbone.Relational.store.unregister(model);
        }
      }

      return Lookup.prototype.remove.call(this, id, options);
    },

    byModel: function(modelOrId) {
      return this._byModelId[this.idOfModel(modelOrId)];
    },

    removeByModel: function(modelOrId, options) {
      return this.remove(this.byModel(modelOrId));
    },

    render: function() {
      this.each(function(v) { v.render(); });
      return this;
    }
  });

  // A self-maintaining, 'flattened' lookup of the views in a group of view
  // collections.
  var ViewCollectionGroup = LookupGroup.extend({
    idOfView: idOfView,
    resolveView: ViewCollection.prototype.resolveView,

    add: function(memberKey, view, options) {
      var member = this.members.get(memberKey);
      return member.add(view, options);
    },

    remove: function(viewOrId, options) {
      var id = this.idOfView(viewOrId),
          member = this.ownerOf(id);

      return member.remove(viewOrId, options);
    },

    render: function() {
      this.members.each(function(collection) { collection.render(); });
      return this;
    }
  });

  // A collection of subviews mapping to an attribute on a view's model.
  //
  // Options:
  // - view: The parent view for this collection of subviews
  // - attr: The attr on the parent view's model which holds the associated
  // collection or model
  // - ViewCollection options
  var SubviewCollection = ViewCollection.extend({
    constructor: function(options) {
      this.view = options.view;
      this.attr = options.attr;
      options.models = this.view.model.get(this.attr);
      ViewCollection.prototype.constructor.call(this, options);
    },

    // Provides a way for each subview to be appended to the parent view.
    appendToView: function(viewOrId) {
      var subview = this.resolveView(viewOrId);
      this.view.$el.append(subview.$el);
    }
  });

  // A self-maintaining, 'flattened' lookup of subview collections defined by a
  // schema.
  //
  // Options:
  // - view: The parent view of the group
  // - [schema]: A list of options for each subview collection. Override to
  // change the subview options passed to each subview collection.
  // - [schemaDefaults]: Defaults to apply to each subview collection option
  // set in the schema
  // - [collectionType]: The default subview collection type
  var SubviewCollectionGroup = ViewCollectionGroup.extend({
    // Override to change the subview collection type
    collectionType: SubviewCollection,

    // A list of specs/options, each a subview collection.
    // Override to change the subview collections are created.
    schema: [{attr: 'subviews'}],

    schemaDefaults: {},

    constructor: function(options) {
      ViewCollectionGroup.prototype.constructor.call(this);

      this.view = options.view;
      this.schema = options.schema || this.schema;
      this.schemaDefaults = options.schemaDefaults || this.schemaDefaults;
      this.collectionType = options.collectionType || this.collectionType;

      // clone each collection option set so we don't modify the schema
      this.schema.forEach(
        function(options) { this.subscribe(_.clone(options)); },
        this);
    },

    subscribe: function(options) {
      _(options).defaults({view: this.view}, _(this).result('schemaDefaults'));

      var collectionType = options.collectionType || this.collectionType,
          collection = new collectionType(options);

      return ViewCollectionGroup
        .prototype
        .subscribe
        .call(this, options.attr, collection);
    }
  });

  _.extend(exports, {
    Extendable: Extendable,
    Eventable: Eventable,
    Lookup: Lookup,
    LookupGroup: LookupGroup,
    ViewCollection: ViewCollection,
    ViewCollectionGroup: ViewCollectionGroup,
    SubviewCollection: SubviewCollection,
    SubviewCollectionGroup: SubviewCollectionGroup
  });
})(go.components.structures = {});
