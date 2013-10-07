describe("go.components.grid", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists,
      oneElExists = testHelpers.oneElExists;

  describe(".GridView", function() {
    var GridView = go.components.grid.GridView;

    var grid;

    var assertRows = function(expectedRows) {
      var actualRows = grid
        .$rows()
        .map(function() {
          return [
           $(this)
             .children()
             .map(function() { return $(this).data('grid:key'); })
             .get()];
        })
        .get();

      assert.deepEqual(actualRows, expectedRows);
    };

    beforeEach(function() {
      grid = new GridView({el: $('<div>').attr('id', 'grid').width(960)});

      ['a', 'b', 'c', 'd', 'e'].forEach(function(k) {
        var item = $('<div>')
          .attr('id', k)
          .css({
            'float': 'left',
            'height': '100px',
            'width': '230px',
            'margin': '5px'
          });

        grid.add(k, item);
      });

      $('body').append(grid.$el);
    });

    afterEach(function() {
      grid.$el.remove();
    });

    describe("on ui item order changes", function() {
      beforeEach(function() {
        grid.render();
      });

      it("re-render the grid with the new ordering", function() {
        assertRows([
          ['a', 'b', 'c', 'd'],
          ['e']]);

        $('#a').simulate('drag', {dy: 150});

        assertRows([
          ['b', 'c', 'd', 'e'],
          ['a']]);
      });
    });

    describe(".render", function() {
      it("should render its items in rows", function() {
        assert.equal(grid.$el.html(), '');

        grid.render();

        assertRows([
          ['a', 'b', 'c', 'd'],
          ['e']]);
      });
    });
  });
});
