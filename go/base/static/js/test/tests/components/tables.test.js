describe("go.components.tables", function() {

  describe(".init", function() {

    var $buttons;
    var $table;
    beforeEach(function() {

      $buttons = $('<div class="buttons"><button disabled="disabled"></div>');

      $table = $('<table><thead></thead><tbody></tbody></table>');
      $table.find('thead').append('<tr><th><input name="h1" type="checkbox"></th><th>head</th></tr>');
      $table.find('tbody').append('<tr data-url="abc"><td><input name="c1" type="checkbox"></td><td>body</td></tr>');
      $table.find('tbody').append('<tr data-url-alt="def"><td><input name="c2" type="checkbox"></td><td>body</td></tr>');

      go.components.tables.init({
        tableSelector: $table,
        checkedToggle: $buttons.find('button')
      });
    });

    it('should propogate events on the td element which holds the checkbox', function() {
      var td = 'tbody tr:first-child td:first-child';
      $table.find(td).trigger('click');
      assert.isTrue($table.find(td).find('input:checkbox').prop('checked'));
      $table.find(td).trigger('click');
      assert.isFalse($table.find(td).find('input:checkbox').prop('checked'));
    });


    it('should `check` the header checkbox when all checkboxes are checked', function() {

      var $checkboxes = $table.find('tbody input:checkbox');
      $checkboxes.each(function() {
        $(this).trigger('click');
      });
      assert.isTrue($table.find('thead input:checkbox').prop('checked'));

    });

    it('elements in `checkToggle` should toggle `disabled`', function() {

      var $cb = $table.find('tbody input:checkbox').eq(0);
      $cb.trigger('click');
      assert.isTrue($cb.prop('checked'));
      assert.isFalse($buttons.find('button').eq(0).prop('disabled'));

      $cb.trigger('click');
      assert.isFalse($cb.prop('checked'));
      assert.isTrue($buttons.find('button').eq(0).prop('disabled'));

    });
  });
});
