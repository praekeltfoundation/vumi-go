// go.components.structures
// ========================
// Reusable, generic structures for Go

(function(exports) {
  var utils = go.utils,
      merge = utils.merge;

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
    addDefaults: {silent: false},
    removeDefaults: {silent: false},

    constructor: function(items) {
      this._items = {};

      items = items || {};
      for (var k in items) { this.add(k, items[k], {silent: true}); }
    },

    size: function() { return _.size(this._items); },

    keys: function() { return _.keys(this._items); },

    values: function() { return _.values(this._items); },

    items: function() { return _.clone(this._items); },

    each: function(fn, that) { return this.values().forEach(fn, that); },

    map: function(fn, that) { return this.values().map(fn, that); },

    eachItem: function(fn, that) {
      var items = this.items();
      for (var k in items) { fn.call(that, k, items[k]); }
    },

    has: function(k) { return _.has(this._items, k); },

    get: function(key) { return this._items[key]; },

    add: function(key, value, options) {
      options = _(options || {}).defaults(this.addDefaults);

      this._items[key] = value;
      if (!options.silent) { this.trigger('add', key, value); }
      return this;
    },

    remove: function(key, options) {
      options = _(options || {}).defaults(this.removeDefaults);

      var value = this._items[key];
      if (value) {
        delete this._items[key];
        if (!options.silent) { this.trigger('remove', key, value); }
      }
      return value;
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
    constructor: function(lookups) {
      Lookup.prototype.constructor.call(this);
      this.members = new Lookup();

      // Lookup of item owners by item keys
      this._owners = {};

      // Lookup of the add callbacks bound to member add events. We only need
      // to bind callbacks for adds and not removes, since we need to know the
      // owner of an item to be added, while with removes, we know already. We
      // keep a lookup so we can unbind the add callbacks when the member is
      // unsubscribed.
      this._memberAdds = {};

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
      this._memberAdds[key] = add;
      this.members.add(key, lookup);

      lookup.eachItem(add);
      lookup.on('add', add);
      lookup.on('remove', this.onMemberRemove, this);
      return this;
    },

    unsubscribe: function(key) {
      var lookup = this.members.get(key),
          add = this._memberAdds[key];

      delete this._memberAdds[key];
      lookup.off('add', add);
      lookup.off('remove', this.onMemberRemove, this);

      lookup.keys().forEach(this.onMemberRemove, this);
      this.members.remove(key);
      return lookup;
    }
  });

  var idOfModel = function(obj) {
    return obj.id
      ? obj.id
      : obj.cid || obj;
  };

  var idOfView = function(obj) {
    return obj.id
      ? _(obj).result('id')
      : obj;
  };

  // Maintains a collection of views, allowing views to be created dynamically
  // and interacted with collectively.
  //
  // Optionally accepts a collection of models, maintaining a corresponding
  // collection of views. New views are created when models are added to the
  // collection, old views are removed when models are removed from the
  // collection.
  //
  // Options:
  // - [models]: the collection of models to create views for
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

    addDefaults: {
      silent: false,
      render: true,  // render view after adding
      addModel: false  // add the model if it is not in the collection
    },

    removeDefaults: {
      silent: false,
      render: true,  // render view after adding
      removeModel: false  // remove the model if it is in the collection
    },

    constructor: function(options) {
      Lookup.prototype.constructor.call(this);
      options = options || {};

      this._byModelId = {};
      this.models = this._ensureCollection(options.models);
      this.models.on('add', function(m) { this.add({model: m}); }, this);
      this.models.on('remove', function(m) { this.removeByModel(m); }, this);

      this.type = options.type || this.type;
      this.typeAttr = this.type.prototype.typeAttr || this.typeAttr;

      this.initialize(options);

      this.models.each(function(m) {
        this.add({
          model: m,
          render: false,
          silent: true
        });
      }, this);
    },

    initialize: function() {},

    _ensureModel: function(obj) {
      return obj instanceof Backbone.Model
        ? obj
        : new this.models.model(obj || {});
    },

    _ensureCollection: function(obj) {
      if (obj instanceof Backbone.Collection) { return obj; }
      if (obj instanceof Backbone.Model) { obj = [obj]; }
      return new Backbone.Collection(obj instanceof Array ? obj : []);
    },

    determineType: function(options) {
      var type = this.type,
          subtypes = type.prototype.subtypes;

      if (!options.model || !subtypes) { return type; }

      var typeName = options.model.get(this.typeAttr);
      return !typeName
        ? type
        : subtypes[typeName] || type;
    },

    // Override to specialise how each view is created
    create: function(options) {
      options = _(options || {}).defaults(_(this).result('viewOptions'));
      var type = this.determineType(options);
      return new type(options);
    },

    add: function(options) {
      options = _(options || {}).defaults(this.addDefaults);

      var model = options.model;
      if (model) {
        options.model = model = this._ensureModel(model);
        if (options.addModel) { this.models.add(model, {silent: true}); }
      }

      var view = this.create(options);
      if (options.render) { view.render(); }

      if (model) { this._byModelId[idOfModel(model)] = view; }
      Lookup.prototype.add.call(this, idOfView(view), view, options);
      return view;
    },

    remove: function(viewOrId, options) {
      options = _(options || {}).defaults(this.removeDefaults);

      var id = idOfView(viewOrId),
          view = this.get(id);

      if (!view) { return; }
      if (typeof view.destroy === 'function') { view.destroy(); }

      var model = view.model;
      if (model) {
        delete this._byModelId[idOfModel(model)];
        if (options.removeModel) { this.models.remove(model, {silent: true}); }
      }

      return Lookup.prototype.remove.call(this, id, options);
    },

    byModel: function(modelOrId) {
      return this._byModelId[idOfModel(modelOrId)];
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
    }
  });

  // A self-maintaining, 'flattened' lookup of subview collections defined by a
  // schema.
  //
  // Arguments:
  // - view: The parent view of the group
  var SubviewCollectionGroup = ViewCollectionGroup.extend({
    // Override to change the subview collection type
    collectionType: SubviewCollection,

    // A list of specs/options, each a subview collection.
    // Override to change the subview collections are created.
    schema: [{attr: 'subviews'}],

    // Defaults to apply to each subview spec/option set
    defaults: {},

    constructor: function(view) {
      ViewCollectionGroup.prototype.constructor.call(this);

      this.view = view;
      this.schema = _(this).result('schema');

      // clone each collection option set so we don't modify the schema
      this.schema.forEach(
        function(options) { this.subscribe(_.clone(options)); },
        this);
    },

    subscribe: function(options) {
      _(options).defaults({view: this.view}, _(this).result('defaults'));

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
