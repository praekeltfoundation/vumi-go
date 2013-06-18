describe("go.components.structures", function() {
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

    beforeEach(function() {
      lookup = new Lookup({a: 1, b: 2, c: 3});
    });

    describe(".size", function() {
      it("should return the lookup's item count", function() {
        assert.deepEqual(lookup.size(), 3);
      });
    });

    describe(".keys", function() {
      it("should get the lookup's item's keys", function() {
        assert.deepEqual(lookup.keys(), ['a', 'b', 'c']);
      });
    });

    describe(".values", function() {
      it("should get the lookup's item's values", function() {
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

    describe(".eachItem", function() {
      it("should iterate through each the lookup's items", function() {
        var items = {};
        lookup.eachItem(function(k, v) { items[k] = v; });
        assert.deepEqual(lookup.items(), items);
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
    });

    describe(".remove", function() {
      it("should remove an item from the lookup", function() {
        assert.equal(lookup.remove('c'), 3);
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
      group = new LookupGroup({'a': lookupA, 'b': lookupB});
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
      it("should add the key value pair", function() {
        group.add(lookupA, 'g', 7);
        assert.equal(group.get('g'), 7);
      });

      it("should add the item to the owner lookup", function() {
        group.add(lookupA, 'g', 7);
        assert.equal(group.ownerOf('g'), lookupA);
      });
    });

    describe(".remove", function() {
      it("should remove the key value pair", function() {
        assert.equal(group.remove('b'), 2);
        assert.isFalse(group.has('b'));
      });

      it("should remove the item from the owner lookup", function() {
        group.remove('b');
        assert.isUndefined(group.ownerOf('b'));
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

  describe(".ViewCollection", function() {
    var ViewCollection = structures.ViewCollection;

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
      models = new Backbone.Collection([{id: 'a'}, {id: 'b'}, {id: 'c'}]);
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
      views = new ViewCollection();
      views.add({id: 'a'});
      views.add({id: 'b'});
      views.add({id: 'c'});

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
        views.add({model: model, addModel: true});
        assert(views.models.get('e'));
      });

      it("should add the view to the 'by model' lookup", function() {
        views.add({model: model});
        assert(views.byModel(model), views.get('d'));
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

      it("should call the view's destroy() function if it exists", function() {
        assert(views.remove('c').destroyed);
      });

      it("should remove the view's model if 'removeModel' is true", function() {
        views.remove('c', {removeModel: true});
        assert.isUndefined(views.models.get('c'));
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
      subviews = new SubthingViewCollections(view);
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
