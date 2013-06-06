// go.components.tables
// ========================
// Tables that are used to manage swaths of data.

(function(exports) {

    var TableFormView = Backbone.View.extend({

        events: {
            'click thead input:checkbox': 'toggleAllCheckboxes',
            'click tbody tr td:first-child input:checkbox': 'onClick',
            'click tbody tr td:first-child': 'onClick',
            'click tbody tr': 'followLink'
        },

        initialize: function() {
            // the table is rendered elsewhere, so el is an absolute
            // requirements.
            if (!this.$el.is('form')) {
                throw("TableFormView must get an `el` attribute that's a FORM element")
            }

            _.defaults(this.options, {
                rowLinkAttribute: 'data-url',
                actionPrefix: '_'
            });

            _.bindAll(this,
                'toggleAllCheckboxes',
                'onClick',
                'onChecked',
                'followLink',
                'showConfirmationModal'
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
            var $this = $(ev.target);

            // the `td` that houses the checkbox is clickable, this make the
            // checkbox easier to click because it increases the target
            // area.
            if ($this.is('td')) {
                $this.find('input:checkbox').trigger('click');
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

        followLink: function(ev) {
            var $this = $(ev.target).parents('tr');
            var url = $this.attr(this.options.rowLinkAttribute);
            if (typeof(url) !== 'undefined') window.location = url;
        },

        showConfirmationModal: function(options) {

            var $cbs = this.$el.find('tbody input:checked');
            var numChecked = $cbs.length;
            var q = "Are you sure you want to <%=action%> this item?";
            if (numChecked > 1) {
                q = "Are you sure you want to <%=action%> these <%=numChecked%> items?";
            }
            var qq = _.template(q);
            var message = qq({
                action: options.action,
                numChecked: numChecked
            });

            var that = this;
            bootbox.confirm(message, function(submit) {
                if (submit === false) return;
                // add an action field to the form; the view to which this
                // submits can use this field to determine which action
                // was envoked.
                that.$el.append('<input type="hidden" name="' +
                    that.options.actionPrefix + options.action + '">');
                that.$el.submit();
            });
        }
    });


    _.extend(exports, {
        TableFormView: TableFormView
    });
})(go.components.tables = {});
