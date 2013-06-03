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

    beforeEach(function() {
      lookupA = new Lookup({a: 1, b: 2, c: 3});
      lookupB = new Lookup({d: 4, e: 5, f: 6});
      group = new LookupGroup({'a': lookupA, 'b': lookupB});
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
          assert.equal(group.get('i'), 9);
          done();
        });

        lookupC.add('i', 9);
      });

      it("should bind the lookup's removes to the groups own removes",
         function(done) {
        var lookupC = new Lookup({g: 7, h: 8});
        group.subscribe('c', lookupC);

        lookupC.on('remove', function(key, value) {
          assert(!group.has('g'));
          done();
        });

        lookupC.remove('g');
      });

      it("should add lookup to the group's member lookup", function() {
        var lookupC = new Lookup({g: 7, h: 8});
        group.subscribe('c', lookupC);
        assert.equal(group.members.get('c'), lookupC);
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
    });
  });

  describe(".ViewCollection", function() {
    var ViewCollection = structures.ViewCollection;

    var models,
        views;

    var ToyView = Backbone.View.extend({
      initialize: function() {
        this.rendered = false;
        this.destroyed = false;
      },

      destroy: function() { this.destroyed = true; },
      render: function() { this.rendered = true; }
    });

    var ToyViewCollection = ViewCollection.extend({
      create: function(options) { return new ToyView(options); }
    });

    var assertAdded = function(id) {
      assert.equal(views.get(id).model, models.get(id));
    };

    var assertRemoved = function(id) {
      assert(!views.has(id));
    };

    beforeEach(function() {
      models = new Backbone.Collection([{id: 'a'}, {id: 'b'}, {id: 'c'}]);
      views = new ToyViewCollection(models);
    });

    describe("on 'add' model collection events", function() {
      it("should add a view corresponding to the model", function(done) {
        models.on('add', function() {
          assertAdded('d');
          done();
        });

        models.add({id: 'd'});
      });
    });

    describe("on 'remove' collection events", function() {
      it("should remove the corresponding view", function(done) {
        models.on('remove', function() {
          assertRemoved('c');
          done();
        });

        models.remove('c');
      });
    });

    describe(".add", function() {
      var modelD;

      beforeEach(function() {
        modelD = new Backbone.Model({id: 'd'});
        models.add(modelD, {silent: true});
      });

      it("should emit an 'add' event", function(done) {
        views.on('add', function(id, view) {
          assert.equal(id, 'd');
          assert.equal(view, views.get('d'));
          done();
        });

        views.add(modelD);
      });

      it("should render the added view", function() {
        views.add(modelD);
        assert(views.get('d').rendered);
      });

      it("should add the model if 'addModel' is true", function() {
        views.add(modelD, {addModel: true});
        assert(views.models.get('d'));
      });
    });

    describe(".remove", function() {
      it("should remove the view", function() {
        views.remove('c');
        assertRemoved('c');
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

      it("should remove the model if 'removeModel' is true", function() {
        views.remove('c', {removeModel: true});
        assert.isUndefined(views.models.get('c'));
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

  var SubviewCollection = structures.SubviewCollection;

  var SubthingView = Backbone.View.extend();

  var SubthingViewCollection = SubviewCollection.extend({
    defaults: {type: SubthingView},

    opts: function() { return {id: this.size()}; },

    constructor: function(options) {
      SubviewCollection.prototype.constructor.call(this, options);
      this.options = options;
    }
  });

  describe(".SubviewCollection", function() {
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

      subviews = new SubthingViewCollection({
        view: view,
        attr: 'subthings'
      });
    });

    it("should be useable with model type attributes", function() {
      subviews = new SubthingViewCollection({
        view: view,
        attr: 'lonelySubthing'
      });

      assert.deepEqual(subviews.keys(), ['d']);
    });

    it("should be useable with collection type attributes", function() {
      subviews = new SubthingViewCollection({
        view: view,
        attr: 'subthings'
      });

      assert.deepEqual(subviews.keys(), ['a', 'b', 'c']);
    });

    describe(".create", function() {
      it("should create subviews of the collection's type", function() {
        subviews.each(function(v) { assert.instanceOf(v, SubthingView); });
      });

      it("should create the view with options defined by the collection",
      function() {
        subviews.each(function(v, i) { assert.equal(v.id, i); });
      });
    });
  });

  describe(".SubviewCollectionGroup", function() {
    var view,
        subviews;

    var SubviewCollectionGroup = structures.SubviewCollectionGroup;

    var SubthingViewCollections = SubviewCollectionGroup.extend({
      collectionType: SubthingViewCollection,

      schema: [
        {attr: 'subthings'},
        {attr: 'lonelySubthing'}]
    });

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

    it("shouldn't allow its schema to be modified during setup", function() {
      var subthings = subviews.members.get('subthings');
      subthings.options.someProp = 23;
      assert.deepEqual(
        subviews.schema,
        [{attr: 'subthings'},
         {attr: 'lonelySubthing'}]);
    });
  });
});
