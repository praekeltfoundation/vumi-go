describe("go.components.tables", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists,
      oneElExists = testHelpers.oneElExists;

  describe(".TableFormView", function() {
    var $buttons,
        $saveModal,
        $form,
        table;

    beforeEach(function() {
      $buttons = $([
        '<div class="buttons">',
          '<button data-action="delete" disabled="disabled">delete</button>',
          '<button data-action="edit" disabled="disabled">edit</button>'
      ].join(''));

      $form = $([
        '<form>',
          '<table>',
            '<thead>',
              '<tr>',
                '<th><input name="h1" type="checkbox"></th>',
                '<th>head</th>',
              '</tr>',
            '</thead>',
            '<tbody>',
              '<tr data-url="abc">',
               '<td><input name="c1" type="checkbox"></td>',
               '<td>body</td>',
              '</tr>',
              '<tr data-url="abc">',
               '<td><input name="c2" type="checkbox"></td>',
               '<td>body</td>',
              '</tr>',
            '</tbody>',
          '</table>',
        '</form>'
      ].join(''));

      table = new go.components.tables.TableFormView({
        actions: $buttons.find('button'),
        el: $form
      });

      bootbox.animate(false);
    });

    afterEach(function() {
      $('.bootbox')
        .hide()
        .remove();
    });

    describe("when the head checkbox is checked", function() {
      it("should toggle the table's body checkboxes", function() {
        assert.equal(table.numChecked(), 0);
        table.$('th:first-child input').prop('checked', true).change();
        assert(table.allChecked());
      });
    });

    describe("when all checkboxes are checked", function() {
      it('should toggle the header checkbox', function() {
        assert.isFalse(table.$('th:first-child input').is(':checked'));
        table.$('tr td:first-child input').prop('checked', true).change();
        assert.isTrue(table.$('th:first-child input').is(':checked'));
      });
    });

    describe("when a checkbox is checked", function() {
      it('should toggle disabled action elements', function() {
        var $marker = table.$('td:first-child input').eq(0),
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

      describe("if the action is targeting a modal", function() {
        var $saveModal;

        beforeEach(function() {
          $buttons.append($([
            '<button ',
             'data-action="save" ',
             'data-toggle="modal" ',
             'data-target="#saveModal" ',
             'disabled="disabled">',
               'save',
             '</button>'
          ].join('')));

          $saveModal = $([
            '<div class="modal hide fade" id="saveModal">',
              '<form method="post" action="">',
                '<div class="modal-body">',
                  'Are you sure you want to save this item?',
                '</div>',
                '<div class="modal-footer">',
                  '<a class="btn" data-dismiss="modal" href="#">Cancel</a>',
                  '<button type="submit">OK</button>',
                '</div>',
              '</form>',
            '</div>'
          ].join(''));

          $('body').append($saveModal);

          table = new go.components.tables.TableFormView({
            actions: $buttons.find('button'),
            el: $form
          });
        });

        afterEach(function() {
          $saveModal.remove();
        });

        it("should submit the action when the modal's form is submitted",
        function(done) {
          assert(noElExists(table.$('[name=_save]')));

          table.$el.submit(function(e) {
            e.preventDefault();
            assert(oneElExists(table.$('[name=_save]')));
            done();
          });

          $saveModal.find('[type=submit]').click();
          assert(noElExists(table.$('[name=_save]')));
        });
      });

      describe("if the action is is not targeting a modal", function() {
        it("should show a confirmation modal", function() {
          assert(noElExists('.modal'));
          $edit.click();
          assert(oneElExists('.modal'));
        });

        it("should submit the action when the action is confirmed",
        function(done) {
          assert(noElExists(table.$('[name=_edit]')));

          table.$el.submit(function(e) {
            e.preventDefault();
            assert(oneElExists(table.$('[name=_edit]')));
            done();
          });

          $edit.click();
          $('.modal').find('[data-handler="1"]').click();

          assert(noElExists(table.$('[name=_edit]')));
        });
      });
    });
  });
});
