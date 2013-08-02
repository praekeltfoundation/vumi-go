describe("go.components.tables", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists,
      oneElExists = testHelpers.oneElExists;

  describe(".TableFormView", function() {
    var $buttons,
        $form,
        table;

    beforeEach(function() {
      $buttons = $([
        '<div class="buttons">',
          '<button data-action="delete" disabled="disabled">delete</button>',
          '<button data-action="edit" disabled="disabled">edit</button>',
        '</div>'
      ].join(''));

      $form = $([
        '<form>',
          '<table>',
            '<thead>',
              '<tr>',
                '<th><input class="action-marker" name="h1" type="checkbox"></th>',
                '<th>head</th>',
              '</tr>',
            '</thead>',
            '<tbody>',
              '<tr data-url="abc">',
               '<td><input class="action-marker" name="c1" type="checkbox"></td>',
               '<td>body</td>',
              '</tr>',
              '<tr data-url="abc">',
               '<td><input class="action-marker" name="c2" type="checkbox"></td>',
               '<td>body</td>',
              '</tr>',
            '</tbody>',
          '</table>',
        '</form>',
      ].join(''));

      table = new go.components.tables.TableFormView({
        el: $form,
        actions: $buttons.find('button')
      });
    });

    afterEach(function() {
      $('.modal').remove();
    });

    describe("when all checkboxes are checked", function() {
      it('should toggle the header checkbox', function() {
        assert.isFalse(table.$('thead .action-marker').is(':checked'));
          table.$('tbody tr td:first-child').click();
        assert.isTrue(table.$('thead .action-marker').is(':checked'));
      });
    });

    describe("when a checkbox is checked", function() {
      it('should toggle disabled action elements', function() {
        var $marker = table.$('tbody .action-marker').eq(0),
            $edit = $buttons.find('[data-action="edit"]');

        // enabled
        $marker.prop('checked', true).change();
        assert(!$edit.is(':disabled'));

        // disabled
        $marker.prop('checked', false).change();
        assert($edit.is(':disabled'));
      });
    });

    describe("when an action button is clicked", function() {
      var $edit;

      beforeEach(function() {
        $edit = $buttons
          .find('[data-action="edit"]')
          .prop('disabled', false);
      });

      it("should show a confirmation modal", function() {
        assert(noElExists('.modal'));
        $edit.click();
        assert(oneElExists('.modal'));
      });

      describe("when the confirmation modal is shown", function() {
        it("should submit the action", function() {
          assert(noElExists(table.$('[name=_edit]')));

          table.$el.submit(function(e) {
            e.preventDefault();
            assert(oneElExists(table.$('[name=_edit]')));
          });

          $edit.click();
          $('.modal').find('[data-handler="1"]').click();

          assert(noElExists(table.$('[name=_edit]')));
        });
      });
    });
  });
});
