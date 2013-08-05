// go.components.tables
// ========================
// Tables that are used to manage swaths of data.

(function(exports) {
  var TableFormView = Backbone.View.extend({
    defaults: {
      rowLinkAttribute: 'data-url',
      actionPrefix: '_'
    },

    templates: {
      singular: _.template(
        "Are you sure you want to <%=action%> this item?"),
      plural: _.template(
        "Are you sure you want to <%=action%> these <%=numChecked%> items?"),
    },

    initialize: function() {
      // the table is rendered elsewhere, so el is an absolute
      // requirements.
      if (!this.$el.is('form')) {
        throw("TableFormView must get an `el` attribute that's a FORM element");
      }

      _(this.options).defaults(this.defaults);

      // the actions are enabled when atleast a single checkbox
      // is selected.
      this.$actions = $(this.options.actions);
      this.$actions.click(this.onAction.bind(this));
    },

    $headActionMarker: function() {
      return this.$('th:first-child input');
    },

    allChecked: function() {
      return !this.$('td:first-child input:not(:checked)').length;
    },

    numChecked: function() {
      return this.$('td:first-child input:checked').length;
    },

    refreshButtons: function() {
      this.$actions.prop('disabled', !this.numChecked());
    },

    showConfirmationModal: function(options) {
      var numChecked = this.numChecked();

      var template = numChecked > 1
        ? this.templates.plural
        : this.templates.singular;

      var message = template({
        action: options.action,
        numChecked: numChecked
      });

      // add an action field to the form; the view to which this
      // submits can use this field to determine which action
      // was envoked.
      var $input = $('<input>')
        .attr('type', 'hidden')
        .attr('name', this.options.actionPrefix + options.action)
        .appendTo(this.$el);

      var $form = this.$el;
      bootbox.confirm(message, function(submit) {
        if (submit) { $form.submit(); }
        $input.remove();
      });
    },

    onAction: function(e) {
      this.showConfirmationModal({action: $(e.target).attr('data-action')});
    },

    events: {
      // select or deselect all the checkboxes based on the state of the 
      // single checkbox in the header.
      'change th:first-child': function(e) {
        this.$headActionMarker().prop('checked', $(e.target).prop('checked'));
        this.refreshButtons();
      },

      'change td:first-child input': function(e) {
        this.$headActionMarker().prop('checked', this.allChecked());
        this.refreshButtons();
      },

      // the `td` that houses the checkbox is clickable, this make the
      // checkbox easier to click because it increases the target
      // area.
      'click td:first-child': function(e) {
        $(e.target).find('input')
          .prop('checked', true)
          .change();
      },

      'click tbody tr td': function(e) {
        var $el = $(e.target).parents('tr'),
            url = $el.attr(this.options.rowLinkAttribute);

        // Follow the link associated with the row
        if (typeof url !== 'undefined') { window.location = url; }
      },

      'click tbody tr td *': function(e) {
        // Prevent the column's click events from propagating to its elements
        e.stopPropagation();
      }
    }
  });

  _.extend(exports, {
    TableFormView: TableFormView
  });
})(go.components.tables = {});
