// go.components.structures
// ========================
// Reusable, generic structures for Go

(function(exports) {
  var merge = go.utils.merge,
      GoError = go.errors.GoError;

  // Acts as a 'base' for class-like objects which can be extended (with the
  // prototype chain set up automatically)
  exports.Extendable = function () {};

  exports.Extendable.extend = function() {
    // Backbone has an internal `extend()` function which it assigns to its
    // structures. We need this function, so we arbitrarily choose
    // `Backbone.Model`, since it has the function we are looking for.
    return Backbone.Model.extend.call(this, merge.apply(this, arguments));
  };

  // A class-like object onto which events can be bound and emitted
  exports.Eventable = exports.Extendable.extend(Backbone.Events);

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
  var Lookup = exports.Lookup = exports.Eventable.extend({
    constructor: function(items) {
      this._items = {};

      items = items || {};
      for (var k in items) { this.add(k, items[k]); }
    },

    keys: function() { return _.keys(this._items); },

    values: function() { return _.values(this._items); },

    items: function() { return _.clone(this._items); },

    has: function(k) { return _.has(this._items, k); },

    get: function(key) { return this._items[key]; },

    add: function(key, value) {
      this._items[key] = value;
      this.trigger('add', key, value);
      return this;
    },

    remove: function(key) {
      var value = this._items[key];
      if (value) {
        delete this._items[key];
        this.trigger('remove', key, value);
      }
      return value;
    }
  });

  // A protected form of a lookup who's collection of items can only be
  // added/removed from internally. Intended to be used as an extendable,
  // abstract structure.
  var ProtectedLookup = exports.ProtectedLookup = Lookup.extend({
    _add: Lookup.prototype.add,

    _remove: Lookup.prototype.remove,

    add: function() {
      throw new GoError("ProtectedLookups cannot be added to externally");
    },

    remove: function() {
      throw new GoError("ProtectedLookups cannot be removed from externally");
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
  exports.LookupGroup = ProtectedLookup.extend({
    constructor: function(lookups) {
      Lookup.prototype.constructor.call(this);

      // Having the members lookup as protected might feel a bit wierd, since
      // we need to access its protected methods externally. However, this
      // allows places that use a `LookupGroup` to check things directly
      // on the members lookup, for eg: `lookup.members.has(k)`, instead of us
      // needing to bloat `LookupGroup` with methods to proxy access to the
      // lookup methods.
      this.members = new ProtectedLookup();

      lookups = lookups || {};
      for (var k in lookups) { this.subscribe(k, lookups[k]); }
    },

    subscribe: function(key, lookup) {
      var items = lookup.items();
      for (var k in items) { this._add(k, items[k]); }

      lookup.on('add', this._add, this);
      lookup.on('remove', this._remove, this);

      this.members._add(key, lookup);
    },

    unsubscribe: function(key) {
      var lookup = this.members.get(key);
      lookup.keys().forEach(this._remove, this);

      lookup.off('add', this._add, this);
      lookup.off('remove', this._remove, this);

      this.members._remove(key);
    }
  });

  // Accepts a collection of models and maintains a corresponding collection of
  // views. New views are created when models are added to the collection, old
  // views are removed when models are removed from the collection. Views can
  // also be looked up by the id of their corresponding models. Useful in
  // situations where views are to be created dynamically (for eg, state views
  // in a state machine diagram).
  //
  // Arguments:
  //   - collection: the collection of models to create views for
  //
  // Events emitted:
  //   - 'add' (id, view) - Emitted when a view is added
  //   - 'remove' (id, view) - Emitted when a view is removed
  exports.ViewCollection = ProtectedLookup.extend({
    addDefaults: {render: true},

    constructor: function(collection) {
      Lookup.prototype.constructor.call(this);

      this.models = collection;
      this.models.each(function(m) { this._add(m, {render: false}); }, this);

      this.models.on('add', this._add, this);
      this.models.on('remove', this._remove, this);
    },

    // Override to specialise how the view is created
    create: function(model) { return new Backbone.View({model: model}); },

    _add: function(model, options) {
      _.defaults(options, this.addDefaults);
      var view = this.create(model);
      Lookup.prototype.add.call(this, model.id, view);
      if (options.render) { view.render(); }
    },

    _remove: function(model) {
      var view = ProtectedLookup.prototype._remove.call(this, model.id);
      if (view && typeof view.destroy === 'function') { view.destroy(); }
      return view;
    },

    render: function() {
      this.values().forEach(function(v) { v.render(); });
    }
  });
})(go.components.structures = {});
