describe("go.components.grid", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists,
      oneElExists = testHelpers.oneElExists;

  describe(".RowItemView", function() {
    var RowItemView = go.components.grid.RowItemView;

    var ToyItemView = Backbone.View.extend({
      className: 'span4',
      render: function() {
        this.$el.text('rendered');
      }
    });

    var item,
        rowItem;

    beforeEach(function() {
      item = new ToyItemView();
      rowItem = new RowItemView({item: item});
    });

    it("should use its item's span class if it has one", function() {
      assert.equal(rowItem.span, 4);
    });

    it("should use a default span if the item has no span class", function() {
      rowItem = new RowItemView({item: new Backbone.View()});
      assert.equal(rowItem.span, 3);
    });

    it("should use a default span if the item has multiple span classes",
    function() {
      rowItem = new RowItemView({
        item: new Backbone.View({className: 'span2 span3'})
      });

      assert.equal(rowItem.span, 3);
    });

    describe(".render", function() {
      it("should render its item", function() {
        assert.equal(rowItem.$el.text(), '');
        rowItem.render();
        assert.equal(rowItem.$el.text(), 'rendered');
      });
    });
  });

  describe(".RowView", function() {
    var RowView = go.components.grid.RowView,
        RowItemView = go.components.grid.RowItemView;

    var item,
        row;

    beforeEach(function() {
      item = new RowItemView({item: new Backbone.View()});
      row = new RowView();
    });

    describe(".add", function() {
      it("should increment the row's span sum the item's span", function() {
        assert.equal(row.spanSum, 0);
        row.add(item);
        assert.equal(row.spanSum, 3);
      });

      it("should add the item to the row", function() {
        assert.deepEqual(row.items, []);
        row.add(item);
        assert.deepEqual(row.items, [item]);
      });
    });
  });

  describe(".RowCollection", function() {
    var RowView = go.components.grid.RowView,
        RowItemView = go.components.grid.RowItemView,
        RowCollection = go.components.grid.RowCollection;

    var item1,
        item2,
        rows;

    beforeEach(function() {
      item1 = new Backbone.View({className: 'span4', id: 'a'});
      item2 = new Backbone.View({className: 'span5', id: 'b'});
      rows = new RowCollection({items: [item1, item2]});
    });

    describe(".addItem", function() {
      var itemsInRow = function(row) {
        return row.items.map(function(rowItem) { return rowItem.item; });
      };

      it("should add the item to the last row", function() {
        var item3 = new Backbone.View({className: 'span3', id: 'c'});

        assert.deepEqual(itemsInRow(rows.last()), [item1, item2]);
        rows.addItem(item3);
        assert.deepEqual(itemsInRow(rows.last()), [item1, item2, item3]);
      });

      it("should create a new row if the last row has no space", function() {
        assert.equal(rows.size(), 1);
        rows.addItem(new Backbone.View({className: 'span4', id: 'c'}));
        assert.equal(rows.size(), 2);
      });
    });
  });

  describe(".GridView", function() {
    var ViewCollection = go.components.structures.ViewCollection,
        GridView = go.components.grid.GridView;

    var ToyView = Backbone.View.extend({
      initialize: function(options) { this.ordinal = options.ordinal; },
      render: function() { this.$el.text(this.id); }
    });

    var ToyViewCollection = ViewCollection.extend({
      type: ToyView,
      ordered: true,
      arrangeable: true
    });

    var assertRows = function() {
      var actualRows = grid.$('.row').map(function() {
        return [$(this)
          .find('.item')
          .map(function() { return $(this).data('item-id'); }).get()];
      }).get();

      var expectedRows = Array.prototype.slice.call(arguments);
      assert.deepEqual(actualRows, expectedRows);
    };

    var items,
        grid;

    beforeEach(function() {
      items = new ToyViewCollection({
        views: [
          {id: 'a', ordinal: 0},
          {id: 'c', ordinal: 2},
          {id: 'd', ordinal: 3},
          {id: 'e', ordinal: 4},
          {id: 'f', ordinal: 5}]
      });

      grid = new GridView({items: items});
    });

    describe("on ui item order changes", function() {
      beforeEach(function() {
        $('body').append("<div id='dummy'></div>");
        $('#dummy').append(grid.$el);
        grid.render();

        $('.item').css({height: '100px', margin: '5px'});
      });

      afterEach(function() {
        $('#dummy').remove();
      });

      it("should rearrange its items according to the ui ordering",
      function() {
        assert.deepEqual(items.keys(), ['a', 'c', 'd', 'e', 'f']);
        $('[data-uuid="item:a"]').simulate('drag', {dy: 205});
        assert.deepEqual(items.keys(), ['c', 'd', 'e', 'f', 'a']);
      });

      it("re-render the grid with the new ordering", function() {
        assertRows(
          ['a', 'c', 'd', 'e'],
          ['f']);

        $('[data-uuid="item:a"]').simulate('drag', {dy: 205});

        assertRows(
          ['c', 'd', 'e', 'f'],
          ['a']);
      });
    });

    describe("on 'add' item events", function() {
      it("should re-render the grid according to the item ordering",
      function(done) {
        items.on('add', function() {
          assertRows(
            ['a', 'b', 'c', 'd'],
            ['e', 'f']);

          done();
        });

        items.add({id: 'b'});
      });
    });

    describe("on 'remove' item events", function() {
      it("should re-render the grid according to the item ordering",
      function(done) {
        items.on('remove', function() {
          assertRows(['a', 'c', 'e', 'f']);
          done();
        });

        items.remove('d');
      });
    });

    describe(".itemOrder", function() {
      it("should return the current ordering of items on the grid", function() {
        grid.render();
        assert.deepEqual(
          grid.itemOrder(),
          ['a', 'c', 'd', 'e', 'f']);
      });
    });

    describe(".render", function() {
      it("should render its rows according to the item ordering",
      function() {
        assert.equal(grid.$el.html(), '');

        grid.render();

        assertRows(
          ['a', 'c', 'd', 'e'],
          ['f']);
      });

      it("should emit a 'render' event", function(done) {
        grid.on('render', function() { done(); });
        grid.render();
      });
    });
  });
});
