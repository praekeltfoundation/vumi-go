describe("go.components.tables", function() {

  describe(".TableFormView", function() {

    var $buttons;
    var $form;
    var tableFormView;
    beforeEach(function() {

      $buttons = $('<div class="buttons"></div>');
      $buttons.append('<button data-action="delete" disabled="disabled">Delete</button');
      $buttons.append('<button data-action="edit" disabled="disabled">Edit</button');

      $form = $('<form><table><thead></thead><tbody></tbody></table></form>');
      $form.find('thead').append('<tr><th><input name="h1" type="checkbox"></th><th>head</th></tr>');
      $form.find('tbody').append('<tr data-url="abc"><td><input name="c1" type="checkbox"></td><td>body</td></tr>');
      $form.find('tbody').append('<tr data-url-alt="def"><td><input name="c2" type="checkbox"></td><td>body</td></tr>');

      tableFormView = new go.components.tables.TableFormView({
        el: $form,
        onCheckedSelector: $buttons.find('button')
      });

      

    });

    it('should toggle the header checkbox when all checkboxes are checked', function() {

      assert.isFalse($form.find('thead input:checkbox').prop('checked'));
      var $cbs = $form.find('tbody tr td:first-child');
      $cbs.trigger('click');
      assert.isTrue($form.find('thead input:checkbox').prop('checked'));
    });

    /*
    it('should execute `onCheckedCallback` event when a checkbox is toggled', function(done) {

      tableFormView.options.onCheckedCallback = function() {
        assert.isTrue($cb.prop('checked'));
        done();
      };

      var $cb = $form.find('tbody input:checkbox').eq(0);
      $cb.trigger('click');
    });

    it('should toggle disabled on elements from `onCheckedSelector.`', function() {

      // enabled
      var $cb = $form.find('tbody input:checkbox').eq(0);
      $cb.trigger('click');
      assert.isTrue($cb.prop('checked'));

      // disabled
      $cb.trigger('click');
      assert.isFalse($cb.prop('checked'));
      assert.isTrue($buttons.find('button').eq(0).prop('disabled'));

    });
    */



  });
});
