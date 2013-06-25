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
      render: function() { this.$el.text(this.id); }
    });

    var ToyViewCollection = ViewCollection.extend({
      type: ToyView,
      ordered: true,
      comparator: function(v1) { return v1.id.charCodeAt(0); }
    });

    var items,
        grid;

    beforeEach(function() {
      items = new ToyViewCollection({
        views: [
          {id: 'a'},
          {id: 'd'},
          {id: 'c'},
          {id: 'f'},
          {id: 'e'}]
      });
      items.sort();

      grid = new GridView({items: items});
    });

    describe("on 'add' item events", function() {
      it("should re-render the grid according to the item ordering",
      function(done) {
        items.on('add', function() {
          assert.equal(grid.$el.html(), [
            '<div class="row" data-uuid="row0">',
              '<div class="span3" data-uuid="a">',
                '<div id="a">a</div>',
              '</div>',
              '<div class="span3" data-uuid="b">',
                '<div id="b">b</div>',
              '</div>',
              '<div class="span3" data-uuid="c">',
                '<div id="c">c</div>',
              '</div>',
              '<div class="span3" data-uuid="d">',
                '<div id="d">d</div>',
              '</div>',
            '</div>',
            '<div class="row" data-uuid="row1">',
              '<div class="span3" data-uuid="e">',
                '<div id="e">e</div>',
              '</div>',
              '<div class="span3" data-uuid="f">',
                '<div id="f">f</div>',
              '</div>',
            '</div>'
          ].join(''));

          done();
        });

        items.add({id: 'b'});
      });
    });

    describe("on 'remove' item events", function() {
      it("should re-render the grid according to the item ordering",
      function(done) {
        items.on('remove', function() {
          assert.equal(grid.$el.html(), [
            '<div class="row" data-uuid="row0">',
              '<div class="span3" data-uuid="a">',
                '<div id="a">a</div>',
              '</div>',
              '<div class="span3" data-uuid="c">',
                '<div id="c">c</div>',
              '</div>',
              '<div class="span3" data-uuid="e">',
                '<div id="e">e</div>',
              '</div>',
              '<div class="span3" data-uuid="f">',
                '<div id="f">f</div>',
              '</div>',
            '</div>'
          ].join(''));

          done();
        });

        items.remove('d');
      });
    });

    describe(".render", function() {
      it("should render its rows according to the item ordering",
      function() {
        assert.equal(grid.$el.html(), '');

        grid.render();

        assert.equal(grid.$el.html(), [
          '<div class="row" data-uuid="row0">',
            '<div class="span3" data-uuid="a">',
              '<div id="a">a</div>',
            '</div>',
            '<div class="span3" data-uuid="c">',
              '<div id="c">c</div>',
            '</div>',
            '<div class="span3" data-uuid="d">',
              '<div id="d">d</div>',
            '</div>',
            '<div class="span3" data-uuid="e">',
              '<div id="e">e</div>',
            '</div>',
          '</div>',
          '<div class="row" data-uuid="row1">',
            '<div class="span3" data-uuid="f">',
              '<div id="f">f</div>',
            '</div>',
          '</div>'
        ].join(''));
      });
    });
  });
});
