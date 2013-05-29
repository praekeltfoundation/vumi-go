describe("go.components.tables", function() {

  describe(".init", function() {

    var $table;
    beforeEach(function() {
      $table = $('<table><thead></thead><tbody></tbody></table>');
      $table.find('thead').append('<tr><th><input name="h1" type="checkbox"></th><th>head</th></tr>');
      $table.find('tbody').append('<tr data-url="abc"><td><input name="c1" type="checkbox"></td><td>body</td></tr>');
      $table.find('tbody').append('<tr data-url-alt="def"><td><input name="c2" type="checkbox"></td><td>body</td></tr>');

      go.components.tables.init({
        tableSelector: $table
      });
    });

    it('should propogate events on the td element which holds the checkbox', function() {
      var td = 'tbody tr:first-child td:first-child';
      $table.find(td).trigger('click');
      assert.equal($table.find(td).find('input:checkbox').prop('checked'), true);
      $table.find(td).trigger('click');
      assert.equal($table.find(td).find('input:checkbox').prop('checked'), false);
    });


    it('should `check` the header checkbox when all checkboxes are checked', function() {

      var $checkboxes = $table.find('tbody input:checkbox');
      $checkboxes.each(function() {
        $(this).trigger('click');
      });
      assert.equal($table.find('thead input:checkbox').prop('checked'), true);

    });
  });
});
