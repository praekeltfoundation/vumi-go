describe("go.components.structures", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists,
      oneElExists = testHelpers.oneElExists;

  var structures = go.components.structures;

  describe(".Extendable", function() {
    var Extendable = structures.Extendable;

    it("should set up the prototype chain correctly", function() {
      var Parent = Extendable.extend(),
          Child = Parent.extend();

       var child = new Child();
       assert.instanceOf(child, Parent);
       assert.instanceOf(child, Child);
    });

    it("should use a constructor function if specified", function() {
      var Thing = Extendable.extend({
        constructor: function (name) { this.name = name; }
      });

      assert.equal(new Thing('foo').name, 'foo');
    });

    it("should default to a parent's constructor", function() {
      var Parent,
          Child;

      Parent = Extendable.extend({
        constructor: function (name) { this.name = name; }
      });
      Child = Parent.extend();

      assert.equal(new Child('foo').name, 'foo');
    });

    it("should accept multiple object arguments", function() {
      var Thing = Extendable.extend({'a': 'one'}, {'b': 'two'}),
          thing = new Thing();

      assert.equal(thing.a, 'one');
      assert.equal(thing.b, 'two');
    });
  });

  describe(".Lookup", function() {
    var Lookup = structures.Lookup,
        lookup;

    var ToyLookup = Lookup.extend({
      ordered: true,
      comparator: function(v) { return v; }
    });

    beforeEach(function() {
      lookup = new ToyLookup({b: 2, a: 1, c: 3});
    });

    describe(".size", function() {
      it("should return the lookup's item count", function() {
        assert.deepEqual(lookup.size(), 3);
      });
    });

    describe(".keys", function() {
      it("should get the lookup's item's keys in order", function() {
        assert.deepEqual(lookup.keys(), ['a', 'b', 'c']);
      });
    });

    describe(".values", function() {
      it("should get the lookup's item's values in order", function() {
        assert.deepEqual(lookup.values(), [1, 2, 3]);
      });
    });

    describe(".each", function() {
      it("should iterate through each lookup item's value", function() {
        var values = [];
        lookup.each(function(v) { values.push(v); });
        assert.deepEqual(lookup.values(), values);
      });
    });

    describe(".map", function() {
      it("should map each lookup's lookup item's value", function() {
        assert.deepEqual(
          lookup.map(function(v) { return v + 1; }),
          [2, 3, 4]);
      });
    });

    describe(".where", function() {
      beforeEach(function() {
        lookup = new Lookup({
          a: {x: 1, y: 2},
          b: {x: 3, y: 2},
          c: {x: 5, y: 6}
        });
      });

      it("should return the items containing the given properties", function() {
        assert.deepEqual(
          lookup.where({y: 2}),
          [lookup.get('a'), lookup.get('b')]);
      });
    });

    describe(".findWhere", function() {
      beforeEach(function() {
        lookup = new Lookup({
          a: {x: 1, y: 2, ordinal: 0},
          b: {x: 3, y: 2, ordinal: 1},
          c: {x: 5, y: 6, ordinal: 2}
        }, {ordered: true});
      });

      it("should return the first item containing the given properties",
      function() {
        assert.deepEqual(lookup.findWhere({y: 2}), lookup.get('a'));
      });
    });

    describe(".eachItem", function() {
      it("should iterate through the lookup's items in order", function() {
        var items = [];
        lookup.eachItem(function(k, v) { items.push({k: k, v: v}); });

        assert.deepEqual(
          items,
          [{k: 'a', v: 1},
           {k: 'b', v: 2},
           {k: 'c', v: 3}]);
      });
    });

    describe(".has", function() {
      it("should determine whether an item exists in the lookup", function() {
        assert.deepEqual(lookup.has('a'), true);
        assert.deepEqual(lookup.has('d'), false);
      });
    });

    describe(".items", function() {
      it("should get a shallow copy of the lookup's items", function() {
        var items = lookup.items();

        items.a = 'one';
        assert.deepEqual(items, {a: 'one', b: 2, c: 3});

        assert.deepEqual(lookup.items(), {a: 1, b: 2, c: 3});
      });
    });

    describe(".get", function() {
      it("should get a value by its key", function() {
        assert.equal(lookup.get('a'), 1);
      });
    });

    describe(".at", function() {
      it("should get the item's value by its index", function() {
        assert.equal(lookup.at(0), 1);
      });

      it("should return undefined if a bad index is given", function() {
        assert.isUndefined(lookup.at(-1));
      });
    });

    describe(".keyAt", function() {
      it("should get the item's key by its index", function() {
        assert.equal(lookup.keyAt(0), 'a');
      });

      it("should return undefined if a bad index is given", function() {
        assert.isUndefined(lookup.keyAt(-1));
      });
    });

    describe(".indexOf", function() {
      it("should get the item's index by its value", function() {
        assert.equal(lookup.indexOf(1), 0);
      });
    });

    describe(".indexOfKey", function() {
      it("should get the item's index by its key", function() {
        assert.equal(lookup.indexOfKey('a'), 0);
      });
    });

    describe(".add", function() {
      it("should add the item to the lookup", function() {
        assert.equal(lookup.add('d', 4), lookup);
        assert.deepEqual(lookup.items(), {a: 1, b: 2, c: 3, d: 4});
      });

      it("should emit an 'add' event", function(done) {
        lookup.on('add', function(key, value) {
          assert.equal(key, 'd');
          assert.equal(value, 4);
          done();
        });

        lookup.add('d', 4);
      });

      it("should sort the lookup", function() {
        lookup.add('d', 0);
        assert.deepEqual(lookup.values(), [0, 1, 2, 3]);
      });
    });

    describe(".remove", function() {
      it("should remove an item from the lookup", function() {
        assert.equal(lookup.remove('c'), 3);
        assert.deepEqual(lookup.keys(), ['a', 'b']);
        assert.deepEqual(lookup.values(), [1, 2]);
        assert.deepEqual(lookup.items(), {a: 1, b: 2});
      });

      it("should emit a 'remove' event", function(done) {
        lookup.on('remove', function(key, value) {
          assert.equal(key, 'c');
          assert.equal(value, 3);
          done();
        });

        lookup.remove('c');
      });
    });

    describe(".sort", function() {
      it("should allow sorting the items using an 'iterator' comparator",
      function() {
        lookup = new ToyLookup();
        lookup.add('a', 3, {sort: false});
        lookup.add('b', 5, {sort: false});
        lookup.add('c', 2, {sort: false});
        lookup.add('d', 9, {sort: false});

        assert.deepEqual(lookup.values(), [3, 5, 2, 9]);
        lookup.sort();
        assert.deepEqual(lookup.values(), [2, 3, 5, 9]);
      });

      it("should allow sorting the items using a 'property' comparator",
      function() {
        var LittleToyLookup = ToyLookup.extend({comparator: 'ordinal'});

        lookup = new LittleToyLookup();
        lookup.add('a', {ordinal: 3}, {sort: false});
        lookup.add('b', {ordinal: 5}, {sort: false});
        lookup.add('c', {ordinal: 2}, {sort: false});
        lookup.add('d', {ordinal: 9}, {sort: false});

        assert.deepEqual(
          lookup.values(),
          [{ordinal: 3},
           {ordinal: 5},
           {ordinal: 2},
           {ordinal: 9}]);

        lookup.sort();

        assert.deepEqual(
          lookup.values(),
          [{ordinal: 2},
           {ordinal: 3},
           {ordinal: 5},
           {ordinal: 9}]);
      });

      it("should allow sorting the items using a 'native sort' comparator",
      function() {
        var LittleToyLookup = ToyLookup.extend({
          comparator: function(v1, v2) { return v1 < v2 ? -1 : 1; }
        });

        lookup = new LittleToyLookup();
        lookup.add('a', 3, {sort: false});
        lookup.add('b', 5, {sort: false});
        lookup.add('c', 2, {sort: false});
        lookup.add('d', 9, {sort: false});

        assert.deepEqual(lookup.values(), [3, 5, 2, 9]);
        lookup.sort();
        assert.deepEqual(lookup.values(), [2, 3, 5, 9]);
      });

      it("should trigger a 'sort' event after sorting", function(done) {
        lookup
          .on('sort', function() { done(); })
          .sort();
      });
    });

    describe(".rearrange", function() {
      var ArrangeableToyLookup = ToyLookup.extend({
        ordered: true,
        comparator: function(v) { return v.ordinal; },

        arrangeable: true,
        arranger: function(v, ordinal) { v.ordinal = ordinal; }
      });

      beforeEach(function() {
        lookup = new ArrangeableToyLookup({
          a: {ordinal: 3},
          b: {ordinal: 5},
          c: {ordinal: 2},
          d: {ordinal: 9}
        });
      });

      it("should rearrange the lookup's items according to the order given",
      function() {
        assert.deepEqual(lookup.keys(), ['c', 'a', 'b', 'd']);
        lookup.rearrange(['d', 'c', 'b', 'a']);
        assert.deepEqual(lookup.keys(), ['d', 'c', 'b', 'a']);
      });
    });
  });

  describe(".LookupGroup", function() {
    var Lookup = structures.Lookup,
        LookupGroup = structures.LookupGroup,
        lookupA,
        lookupB,
        group;

    var assertAdded = function(owner, key, value) {
      assert.equal(group.get(key), value);
      assert.equal(group.ownerOf(key), owner);
    };

    var assertRemoved = function(key) {
      assert.isFalse(group.has(key));
      assert.isUndefined(group.ownerOf(key));
    };

    beforeEach(function() {
      lookupA = new Lookup({a: 1, b: 2, c: 3});
      lookupB = new Lookup({d: 4, e: 5, f: 6});
      group = new LookupGroup({a: lookupA, b: lookupB});
    });

    describe("on member 'add' events", function() {
      it("should add the key value pair", function(done) {
        lookupA.on('add', function() {
          assert.equal(group.get('g'), 7);
          done();
        });

        lookupA.add('g', 7);
      });

      it("should add the item to the owner lookup", function(done) {
        lookupA.on('add', function() {
          assert.equal(group.ownerOf('g'), lookupA);
          done();
        });

        lookupA.add('g', 7);
      });
    });

    describe("on member 'remove' events", function() {
      it("should remove the key value pair", function(done) {
        lookupA.on('remove', function() {
          assert(!group.has('b'));
          done();
        });

        lookupA.remove('b');
      });

      it("should remove the item from the owner lookup", function(done) {
        lookupA.on('remove', function() {
          assert.isUndefined(group.ownerOf('b'));
          done();
        });

        lookupA.remove('b');
      });
    });

    describe(".ownerOf", function() {
      it("should retrieve the member that owns an item", function() {
        assert.equal(group.ownerOf('c'), lookupA);
      });

      it("should return undefined if no owner is found", function() {
        assert.isUndefined(group.ownerOf('g'));
      });
    });

    describe(".add", function() {
      it("should delegate the add operation to the relevant member",
      function(done) {
        lookupA.on('add', function(k, v) {
          assert.equal(k, 'g');
          assert.equal(v, 7);
          done();
        });

        assert.equal(group.add('a', 'g', 7), group);
      });
    });

    describe(".remove", function() {
      it("should delegate the remove operation to the relevant member",
      function(done) {
        lookupA.on('remove', function(k, v) {
          assert.equal(k, 'b');
          assert.equal(v, 2);
          done();
        });

        assert.equal(group.remove('b'), 2);
      });
    });

    describe(".subscribe", function() {
      it("should add all the lookup's items to the group", function() {
        assert.equal(group.subscribe('c', new Lookup({g: 7, h: 8})), group);
        assert.equal(group.get('g'), 7);
        assert.equal(group.get('h'), 8);
      });

      it("should bind the lookup's adds to the groups own adds",
         function(done) {
        var lookupC = new Lookup({g: 7, h: 8});
        group.subscribe('c', lookupC);

        lookupC.on('add', function(key, value) {
          assertAdded(lookupC, 'i', 9);
          done();
        });

        lookupC.add('i', 9);
      });

      it("should bind the lookup's removes to the groups own removes",
         function(done) {
        var lookupC = new Lookup({g: 7, h: 8});
        group.subscribe('c', lookupC);

        lookupC.on('remove', function(key, value) {
          assertRemoved('g');
          done();
        });

        lookupC.remove('g');
      });

      it("should add lookup to the group's member lookup", function() {
        var lookupC = new Lookup({g: 7, h: 8});
        group.subscribe('c', lookupC);
        assert.equal(group.members.get('c'), lookupC);
      });

      it("should add the items to the owner lookup", function() {
        var lookupC = new Lookup({g: 7, h: 8});
        group.subscribe('c', lookupC);

        lookupC.keys().forEach(function(k) {
          assert.equal(group.ownerOf(k), lookupC);
        });
      });
    });

    describe(".unsubscribe", function() {
      it("should remove all the lookup's items from the group", function() {
        assert.equal(group.unsubscribe('b'), lookupB);
        assert(!group.has('d'));
        assert(!group.has('e'));
        assert(!group.has('f'));
      });

      it("should unbind the lookup's adds from the groups own adds",
         function(done) {
        group.unsubscribe('b');

        lookupB.on('add', function(key, value) {
          assert(!group.has('i'));
          done();
        });

        lookupB.add('i', 9);
      });

      it("should unbind the lookup's removes from the groups own removes",
         function(done) {
        group.unsubscribe('b');
        group.subscribe('c', new Lookup({d: 'four'}));

        lookupB.on('remove', function(key, value) {
          // assert that the item is still there
          assert.equal(group.get('d'), 'four');
          done();
        });

        lookupB.remove('d');
      });

      it("should remove the lookup from the group's member lookup", function() {
        group.unsubscribe('b');
        assert(!group.members.has('b'));
      });

      it("should remove the items from the owner lookup", function() {
        var lookupB = group.unsubscribe('b');

        lookupB.keys().forEach(function(k) {
          assert.isUndefined(group.ownerOf(k));
        });
      });
    });
  });

  describe(".ViewCollectionGroup", function() {
    var ViewCollection = structures.ViewCollection,
        ViewCollectionGroup = structures.ViewCollectionGroup;

    var collectionA,
        collectionB,
        group;

    beforeEach(function() {
      collectionA = new ViewCollection({
        views: [
          {id: 'a'},
          {id: 'b'},
          {id: 'c'}]
      });

      collectionB = new ViewCollection({
        views: [
          {id: 'd'},
          {id: 'e'},
          {id: 'f'}]
      });

      group = new ViewCollectionGroup({a: collectionA, b: collectionB});
    });

    describe(".add", function() {
      it("should delegate the add operation to the relevant collection",
      function(done) {
        var g = new Backbone.View({id: 'g'});

        collectionA.on('add', function(id, view) {
          assert.equal(id, 'g');
          assert.equal(view, g);
          done();
        });

        assert.equal(group.add('a', g), g);
      });
    });

    describe(".remove", function() {
      it("should delegate the remove operation to the relevant collection",
      function(done) {
        var b = group.get('b');

        collectionA.on('remove', function(id, view) {
          assert.equal(id, 'b');
          assert.equal(view, b);
          done();
        });

        assert.equal(group.remove('b'), b);
      });
    });
  });

  describe(".ViewCollection", function() {
    var ViewCollection = structures.ViewCollection;

    var ToyModel = Backbone.RelationalModel.extend({
      subModelTypes: {
        pirate: 'globals.ToyPirateModel',
        ninja: 'globals.ToyNinjaModel'
      }
    });

    var ToyPirateModel = globals.ToyPirateModel = ToyModel.extend(),
        ToyNinjaModel = globals.ToyNinjaModel = ToyModel.extend();

    var ToyView = Backbone.View.extend({
      id: function() { return this.model.id; },
      initialize: function(options) {
        this.i = options.i;
        this.destroyed = false;
        this.rendered = false;
      },
      destroy: function() { this.destroyed = true; },
      render: function() { this.rendered = true; }
    });

    var ToyPirateView = ToyView.extend(),
        ToyNinjaView = ToyView.extend();

    ToyView.prototype.subtypes = {
      pirate: ToyPirateView,
      ninja: ToyNinjaView
    };

    var ToyViewCollection = ViewCollection.extend({
      type: ToyView,
      viewOptions: function() { return {i: this.i++}; },
      initialize: function() { this.i = 0; }
    });

    var models,
        views;

    beforeEach(function() {
      models = new Backbone.Collection(
        [{id: 'a'}, {id: 'b'}, {id: 'c'}],
        {model: ToyModel});

      views = new ToyViewCollection({models: models});
    });

    describe("on 'add' model collection events", function() {
      it("should add a view corresponding to the model", function(done) {
        models.on('add', function(m) {
          assert.equal(views.get('d').model, models.get('d'));
          done();
        });

        models.add({id: 'd'});
      });
    });

    describe("on 'remove' collection events", function() {
      it("should remove the corresponding view", function(done) {
        models.on('remove', function() {
          assert(!views.has('c'));
          done();
        });

        models.remove('c');
      });
    });

    it("should be useable with a single model", function() {
      views = new ToyViewCollection({models: new Backbone.Model({id: 'a'})});
      assert.deepEqual(views.keys(), ['a']);
    });

    it("should be useable with model collections", function() {
      views = new ToyViewCollection({models: models});
      assert.deepEqual(views.keys(), ['a', 'b', 'c']);
    });

    it("should be useable without models", function() {
      views = new ViewCollection({
        views: [
          {id: 'a'},
          {id: 'b'},
          {id: 'c'}]
      });

      assert.deepEqual(views.keys(), ['a', 'b', 'c']);
    });

    describe(".add", function() {
      var model;

      beforeEach(function() {
        model = new Backbone.Model({id: 'd'});
        models.add(model, {silent: true});
      });

      it("should emit an 'add' event", function(done) {
        views.on('add', function(id, view) {
          assert.equal(id, 'd');
          assert.equal(view, views.get('d'));
          done();
        });

        views.add({model: model});
      });

      it("should render the added view", function() {
        views.add({model: model});
        assert(views.get('d').rendered);
      });

      it("should add the model if 'addModel' is true", function() {
        model = new Backbone.Model({id: 'e'});
        views.add({model: model}, {addModel: true});
        assert(views.models.get('e'));
      });

      it("should work with models with subtypes", function() {
        var v = views.add({model: {type: 'ninja'}}, {addModel: true});
        assert.instanceOf(v.model, ToyNinjaModel);
      });

      it("should add the view to the 'by model' lookup", function() {
        views.add({model: model});
        assert(views.byModel(model), views.get('d'));
      });

      it("should accept a view instance", function() {
        var v = new ToyView({id: '23'});
        views.add(v);
        assert.equal(views.get('23'), v);
      });
    });

    describe(".remove", function() {
      it("should remove a view by it's id", function() {
        views.remove('c');
        assert(!views.has('c'));
      });

      it("should remove the given view", function() {
        views.remove(views.get('c'));
        assert(!views.has('c'));
      });

      it("should emit a 'remove' event", function(done) {
        var viewC = views.get('c');

        views.on('remove', function(id, view) {
          assert.equal(id, 'c');
          assert.equal(view, viewC);
          done();
        });

        views.remove('c');
      });

      it("should call the view's destroy() method if it exists", function() {
        assert(views.remove('c').destroyed);
      });

      it("should pass options to the view's .destroy() method", function() {
        var destroyOptions;

        var ToyView = Backbone.View.extend({
          id: function() {
            return this.model.id;
          },
          destroy: function(options) {
            destroyOptions = options;
          }
        });

        var views = new ToyViewCollection({
          type: ToyView,
          models: models
        });

        assert.isUndefined(destroyOptions);
        views.remove('a', {foo: 23});
        assert.equal(destroyOptions.foo, 23);
      });

      it("should remove the view's model if 'removeModel' is true", function() {
        views.remove('c', {removeModel: true});
        assert.isUndefined(views.models.get('c'));
      });

      it("should unregister the model from the relational model store", function() {
        var SubthingModel = Backbone.RelationalModel.extend();

        var ThingModel = Backbone.RelationalModel.extend({
          relations: [{
            type: Backbone.HasMany,
            key: 'subthings',
            relatedModel: SubthingModel
          }]
        });

        var thing = new ThingModel({subthings: {id: 'subthing'}}),
            subthings = thing.get('subthings'),
            subthing = subthings.get('subthing'),
            storeSubthings = Backbone.Relational.store.getCollection(subthing);

        var views = new ViewCollection({
          type: ToyView,
          models: subthings
        });

        assert.isDefined(storeSubthings.get('subthing'));
        views.remove('subthing', {removeModel: true});
        assert.isUndefined(storeSubthings.get('subthing'));
      });

      it("should remove the view from the 'by model' lookup", function() {
        var model = views.models.get('c');
        views.remove('c');
        assert.isUndefined(views.byModel(model));
      });
    });

    describe(".create", function() {
      it("should create a view of the given type", function() {
        var model = new Backbone.Model(),
            view = views.create({model: model});

        assert.instanceOf(view, ToyView);
        assert.equal(view.model, model);
      });

      it("should allow views to define subtypes by name", function() {
        var StarWarsView = Backbone.View.extend({
          subtypes: {
            jedi: 'globals.JediView',
            sith: 'globals.SithView'
          }
        });

        var views = new ViewCollection({type: StarWarsView, models: models});

        globals.JediView = StarWarsView.extend();
        globals.SithView = StarWarsView.extend();

        assert.instanceOf(
          views.create({model: new Backbone.Model({type: 'jedi'})}),
          globals.JediView);

        assert.instanceOf(
          views.create({model: new Backbone.Model({type: 'sith'})}),
          globals.SithView);
      });

      it("should work with views with subtypes", function() {
        assert.instanceOf(
          views.create({model: new Backbone.Model({type: 'pirate'})}),
          ToyPirateView);

        assert.instanceOf(
          views.create({model: new Backbone.Model({type: 'ninja'})}),
          ToyNinjaView);
      });

      it("should default to the base type if no subtypes match the model type",
      function() {
        assert.instanceOf(
          views.create({model: new Backbone.Model({type: 'acid'})}),
          ToyView);
      });

      it("should work with views without subtypes", function() {
        var ViewWithoutSubtypes = Backbone.View.extend();

        var views = new ViewCollection({
          models: models,
          type: ViewWithoutSubtypes
        });

        assert.instanceOf(
          views.create({model: new Backbone.Model()}),
          ViewWithoutSubtypes);
      });

      it("create the view with the specified default options", function() {
        var v1 = views.create({model: new Backbone.Model()}),
            v2 = views.create({model: new Backbone.Model()});

        assert.equal(v1.i, '3');
        assert.equal(v2.i, '4');
      });
    });

    describe(".byModel", function() {
      it("should look up a view by its model's id", function() {
        assert.equal(views.byModel('a'), views.get('a'));
      });

      it("should look up a view by its model", function() {
        assert.equal(views.byModel(views.models.get('a')), views.get('a'));
      });
    });

    describe(".removeByModel", function() {
      it("should remove a view by its model's id", function() {
        var a = views.get('a');
        assert.equal(views.removeByModel('a'), a);
        assert(!views.has('a'));
      });

      it("should remove a view by its model", function() {
        var a = views.get('a');
        assert.equal(views.removeByModel(views.models.get('a')), a);
        assert(!views.has('a'));
      });
    });

    describe(".render()", function() {
      it("should render all the views in the collection", function() {
        views.values().forEach(function(v) { v.rendered = false; });
        views.render();
        views.values().forEach(function(v) { assert(v.rendered); });
      });
    });
  });

  describe(".SubviewCollection", function() {
    var SubviewCollection = structures.SubviewCollection;

    var SubthingView = Backbone.View.extend({
      id: function() { return this.model.id; }
    });

    var view,
        subviews;

    beforeEach(function() {
      var model = new Backbone.Model({
        subthings: new Backbone.Collection([
          {id: 'a'},
          {id: 'b'},
          {id: 'c'}
        ])
      });

      view = new Backbone.View({model: model});
      subviews = new SubviewCollection({
        view: view,
        attr: 'subthings',
        type: SubthingView
      });
    });

    it("should create a collection of subviews from the given view and attr",
    function() {
      assert.deepEqual(subviews.keys(), ['a', 'b', 'c']);
      subviews.each(function(v) { assert.instanceOf(v, SubthingView); });
    });

    describe(".appendToView", function() {
      it("should should append the subview to the parent view", function() {
        assert(noElExists(view.$('#a')));
        subviews.appendToView('a');
        assert(oneElExists(view.$('#a')));
      });
    });
  });

  describe(".SubviewCollectionGroup", function() {
    var SubviewCollection = structures.SubviewCollection,
        SubviewCollectionGroup = structures.SubviewCollectionGroup;

    var SubthingView = Backbone.View.extend({
      id: function() { return this.model.id; }
    });

    var SubthingViewCollection = SubviewCollection.extend({
      type: SubthingView,
      initialize: function(options) { this.options = options; }
    });

    var LonelySubthingViewCollection = SubthingViewCollection.extend();

    var SubthingViewCollections = SubviewCollectionGroup.extend({
      collectionType: SubthingViewCollection,

      schema: [{
        attr: 'subthings'
      }, {
        attr: 'lonelySubthing',
        collectionType: LonelySubthingViewCollection
      }]
    });

    var view,
        subviews;

    beforeEach(function() {
      var model = new Backbone.Model({
        subthings: new Backbone.Collection([
          {id: 'a'},
          {id: 'b'},
          {id: 'c'}
        ]),
        lonelySubthing: new Backbone.Model({id: 'd'})
      });

      view = new Backbone.View({model: model});
      subviews = new SubthingViewCollections({view: view});
    });

    it("should set up the subviews according to the schema", function() {
      assert.deepEqual(subviews.keys(), ['a', 'b', 'c', 'd']);

      assert.deepEqual(
        subviews
          .members
          .get('subthings')
          .keys(),
        ['a', 'b', 'c']);

      assert.deepEqual(
        subviews
          .members
          .get('lonelySubthing')
          .keys(),
        ['d']);
    });

    it("should allow the view collection type to be configured in the schema",
    function() {
      assert.instanceOf(subviews.members.get('subthings'),
                        SubthingViewCollection);

      assert.instanceOf(subviews.members.get('lonelySubthing'),
                        LonelySubthingViewCollection);
    });

    it("shouldn't allow its schema to be modified during setup", function() {
      var subthings = subviews.members.get('subthings');
      subthings.options.someProp = 23;
      assert.deepEqual(
        subviews.schema,
        [{
          attr: 'subthings'
        }, {
          attr: 'lonelySubthing',
          collectionType: LonelySubthingViewCollection
        }]);
    });
  });
});
