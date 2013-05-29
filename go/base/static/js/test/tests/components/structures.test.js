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
    var ViewCollection = structures.ViewCollection,
        models,
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
      create: function(model) { return new ToyView({model: model}); }
    });

    beforeEach(function() {
      models = new Backbone.Collection([{id: 'a'}, {id: 'b'}, {id: 'c'}]);
      views = new ToyViewCollection(models);
    });

    describe("on 'add' collection events", function() {
      it("should add a view corresponding to the model", function(done) {
        models.on('add', function() {
          assert.equal(views.get('d').model, models.get('d'));
          done();
        });

        models.add({id: 'd'});
      });

      it("should emit an 'add' event", function(done) {
        views.on('add', function(id, view) {
          assert.equal(id, 'd');
          assert.equal(view, views.get('d'));
          done();
        });

        models.add({id: 'd'});
      });

      it("should render the added view", function(done) {
        models.on('add', function() {
          assert(views.get('d').rendered);
          done();
        });

        models.add({id: 'd'});
      });
    });

    describe("on 'remove' collection events", function() {
      it("should remove the corresponding view", function(done) {
        models.on('remove', function() {
          assert.isUndefined(views.get('c'));
          done();
        });

        models.remove('c');
      });

      it("should emit a 'remove' event", function(done) {
        var viewC = views.get('c');

        views.on('remove', function(id, view) {
          assert.equal(id, 'c');
          assert.equal(view, viewC);
          done();
        });

        models.remove('c');
      });

      it("should call the view's destroy() function if it exists",
         function(done) {
        var viewC = views.get('c');

        models.on('remove', function() {
          assert(viewC.destroyed);
          done();
        });

        models.remove('c');
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
});
