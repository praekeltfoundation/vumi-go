// go.components.tables
// ========================
// Tables that are used to manage swaths of data.

(function(exports) {

    var TableView = Backbone.View.extend({

        events: {
            'click thead input:checkbox': 'toggleAllCheckboxes',
            'click tbody input:checkbox': 'onClick',
            'click tbody tr td:first-child': 'onClick',
            'click tbody tr': 'openRow'
        },

        initialize: function() {
            // the table is rendered elsewhere, so el is an absolute
            // requirements.
            if (this.$el.length === 0) {
                throw('You must pass and `el` attribute to TableView.');
            }

            _.defaults(this.options, {
                rowLinkAttribute: 'data-url'
            });

            _.bindAll(this,
                'toggleAllCheckboxes',
                'onClick',
                'onChecked',
                'openRow'
            );

            this.on('onChecked', this.onChecked);
        },

        // select or deselect all the checkboxes based on the state of the 
        // single checkbox in the header.
        toggleAllCheckboxes: function(ev) {
            this.$el.find('tbody input:checkbox').prop('checked',
                $(ev.target).prop('checked'));

            this.trigger('onChecked');
        },

        onClick: function(ev) {
            ev.stopPropagation();
            $this = $(ev.target);

            // the `td` that houses the checkbox is clickable, this make the
            // checkbox easier to click because it increases the target
            // area.
            if ($this.is('td')) {
                $this.find('input:checkbox').trigger('click');
                return false;
            }

            this.trigger('onChecked');
        },

        onChecked: function() {

            // determine if all the checkboxes are selected
            var allChecked = true;
            var numChecked = 0;
            this.$el.find('tbody input:checkbox').each(function() {
                if (!$(this).prop('checked')) {
                    // one of our checkboxes isn't checked.
                    allChecked = false;
                } else {
                    numChecked += 1;
                }
            });

            this.$el.find('thead input:checkbox').prop('checked', allChecked);

            var selector = this.options.onCheckedSelector;
            if (typeof(selector) !== 'undefined') {
                $(selector).prop('disabled', numChecked <= 0);
            }
            var callback = this.options.onCheckedCallback;
            if (typeof(callback) !== 'undefined') {
                callback.call(this, allChecked, numChecked);
            }
        },

        openRow: function(ev) {
            var $this = $(ev.target).parents('tr');
            var url = $this.attr(this.options.rowLinkAttribute);
            if (typeof(url) !== 'undefined') window.location = url;
        }

    });


    _.extend(exports, {
        TableView: TableView
    });
})(go.components.tables = {});
