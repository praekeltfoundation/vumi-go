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

  describe(".RowView", function() {
    var RowView = go.components.tables.RowView;

    var row;

    beforeEach(function() {
      row = new RowView({
        model: new Backbone.Model({
          a: 'foo',
          b: 'bar',
          c: 'baz'
        })
      });
    });

    afterEach(function() {
      row.remove();
    });

    describe(".matches", function() {
      it("should return whether the query matches the row's model's attributes",
      function() {
        assert(row.matches({
          a: 'foo',
          b: 'bar',
          c: 'baz'
        }));

        assert(row.matches({
          a: 'foo',
          b: 'bar'
        }));

        assert(row.matches({
          a: 'fo',
          b: 'ba',
          c: 'ba'
        }));

        assert(!row.matches({
          a: 'foo',
          b: 'baz'
        }));
      });

      it("should handle space delimited patterns as multiple queries", function() {
        assert(row.matches({a: 'foo lorem'}));
      });

      it("should support regexes", function() {
        assert(row.matches({a: /fo/}));
        assert(!row.matches({a: /fm/}));
      });
    });
  });

  describe(".TableView", function() {
    var TableView = go.components.tables.TableView,
        RowView = go.components.tables.RowView;

    var ToyRowView = RowView.extend({
      render: function() {
        this.$el.empty();

        _(this.model.attributes)
          .keys()
          .sort()
          .forEach(function(a) {
            this.$el.append($('<td>').text(this.model.get(a)));
          }, this);
      }
    });

    var table;

    beforeEach(function() {
      table = new TableView({
        rowType: ToyRowView,
        columnTitles: ['A', 'B', 'C'],
        models: new Backbone.Collection([{
          a: 'foo',
          b: 'bar',
          c: 'baz'
        }, {
          a: 'lerp',
          b: 'larp',
          c: 'lorem'
        }, {
          a: 'Hypothetical',
          b: 'Basking',
          c: 'Shark'
        }])
      });
    });
    
    afterEach(function() {
      table.remove();
    });

    it("should set up the table head", function() {
      assert.equal(table.$('thead').html(), [
        '<tr>',
          '<th>A</th>',
          '<th>B</th>',
          '<th>C</th>',
        '</tr>'
      ].join(''));
    });

    describe(".render", function() {
      describe("when no query is given", function() {
        it("should render all its rows", function() {
          assert(noElExists(table.$('tbody tr')));

          table.render();

          assert.equal(table.$('tbody').html(), [
            '<tr>',
              '<td>foo</td>',
              '<td>bar</td>',
              '<td>baz</td>',
            '</tr>',

            '<tr>',
              '<td>lerp</td>',
              '<td>larp</td>',
              '<td>lorem</td>',
            '</tr>',

            '<tr>',
              '<td>Hypothetical</td>',
              '<td>Basking</td>',
              '<td>Shark</td>',
            '</tr>'
          ].join(''));
        });
      });

      describe("when a query is given", function() {
        it("should render the matching rows", function() {
          assert(noElExists(table.$('tbody tr')));

          table.render({a: 'foo lerp'});

          assert.equal(table.$('tbody').html(), [
            '<tr>',
              '<td>foo</td>',
              '<td>bar</td>',
              '<td>baz</td>',
            '</tr>',

            '<tr>',
              '<td>lerp</td>',
              '<td>larp</td>',
              '<td>lorem</td>',
            '</tr>'
          ].join(''));
        });
      });
    });
  });
});
