describe("go.components.tables", function() {

  describe(".TableView", function() {

    var $buttons;
    var $table;
    var tableView;
    beforeEach(function() {

      $buttons = $('<div class="buttons"><button disabled="disabled"><button disabled="disabled"></div>');

      $table = $('<table><thead></thead><tbody></tbody></table>');
      $table.find('thead').append('<tr><th><input name="h1" type="checkbox"></th><th>head</th></tr>');
      $table.find('tbody').append('<tr data-url="abc"><td><input name="c1" type="checkbox"></td><td>body</td></tr>');
      $table.find('tbody').append('<tr data-url-alt="def"><td><input name="c2" type="checkbox"></td><td>body</td></tr>');

      tableView = new go.components.tables.TableView({
        el: $table,
        onCheckedSelector: $buttons.find('button'),
      });
    });

    it('should toggle the header checkbox when all checkboxes are checked', function() {

      assert.isFalse($table.find('thead input:checkbox').prop('checked'));
      var $cbs = $table.find('tbody tr td:first-child');
      $cbs.trigger('click');

      assert.isTrue($table.find('thead input:checkbox').prop('checked'));
    });

    it('should execute `onCheckedCallback` event when a checkbox is toggled', function() {

      tableView.options.onCheckedCallback = function() {
        assert.isTrue($cb.prop('checked'));
        done();
      }

      var $cb = $table.find('tbody input:checkbox').eq(0);
      $cb.trigger('click');
    });
    
    it('elements in `onCheckedSelector` should toggle `disabled`', function() {

      // enabled
      var $cb = $table.find('tbody input:checkbox').eq(0);
      $cb.trigger('click');
      assert.isTrue($cb.prop('checked'));
        
      // disabled
      $cb.trigger('click');
      assert.isFalse($cb.prop('checked'));
      assert.isTrue($buttons.find('button').eq(0).prop('disabled'));

    });

    


  });
});
