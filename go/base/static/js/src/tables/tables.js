(function(exports) {

    var init = function(selector) {
        $table = $(selector);

        $table.find('input[type="checkbox"]').click(function(e) {

            e.stopPropagation()

            $this = $(this);
            $tbody = $table.find('tbody');
            $checkboxes = $tbody.find('input[type="checkbox"]');

            // select all / none defined as the checkbox in thead.
            if ($this.parents('thead').length) {
                $checkboxes.prop('checked', $this.prop('checked'));
            }
        
            // used to determine state of thead checkbox
            var allChecked = true;
            // used to determine disabled state of buttons;
            // buttons are linked to table via data-table-id
            // attribute.
            var oneChecked = false;
            $checkboxes.each(function() {
                if (!$(this).is(':checked')) {
                    allChecked = false;
                } else {
                    oneChecked = true;
                }

                // I'm sharing a loop to check for both of these
                // states, once the condition is met I can just
                // abort the loop.
                if (allChecked == false && oneChecked == true) {
                    return false;
                }
            });
            $table.find('thead input[type="checkbox"]').prop('checked', allChecked)

            // toggle the buttons associated with this table;
            // association happens via data-table-id
            $('button[data-table-id="' + $table.attr('data-table-id') + '"]')
                .prop('disabled', !oneChecked);
        });


        $table.find('tr td').not(':first-child').click(function() {
            var url = $(this).parents('tr').attr('data-url');
            if (url.length) window.location = url;
        });
    }

    exports.init = init;


})(go.tables = {});


