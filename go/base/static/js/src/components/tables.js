// go.components.tables
// ========================
// Tables that are used to manage swaths of data.

(function(exports) {


    var init = function(options) {

        var opts = {
            tableSelector: '.components-table',
            linkAttribute: 'data-url'
        };
        $.extend(opts, options);

        var $table = $(opts.tableSelector);
        var $checkboxes = $table.find('input:checkbox');

        // increase the target area of the checkbox by making the the td 
        // element within which it's held clickable.
        $checkboxes.parent().click(function(e) {
            e.stopPropagation();
            var $cb = $(this).find('input[type="checkbox"]').click();
        });

        $checkboxes.click(function(e) {
            e.stopPropagation();

            var $cb = $(this);
            var $checkboxes = $table.find('tbody input:checkbox');

            // the checkbox in the table's header was selected, so deselect
            // or select or children rows accordingly.
            if ($cb.parents('thead').length) {
                $checkboxes.prop('checked', $cb.prop('checked'));
            }

            // if all the $checkboxes are selected then we should update the 
            // state of the header checkbox to reflect that.
            var allChecked = true;
            var oneChecked = false;
            $checkboxes.each(function() {
                if (!$(this).prop('checked')) {
                    // one of our checkboxes isn't checked.
                    allChecked = false;
                } else {
                    oneChecked = true;
                }
                // once the below condition is proved then I no longer need
                // this loop, you're either this below or the defaults that
                // we set at the start of the loop.
                if (!allChecked && oneChecked) {
                    return false;
                }
            });
            $table.find('thead input:checkbox').prop('checked', allChecked);


            // the user of the table passes in a selector of elements that they
            // want `enabled` when one of the checkboxes is checked, here we
            // enable or disable based on `oneChecked`.
            if (typeof(opts.checkedToggle) !== 'undefined') {
                $(opts.checkedToggle).prop('disabled', !oneChecked);
            }
        });

        // the entire row of the table should act as a link, except for the
        // header row.
        $table.find('tbody tr').click(function() {
            var url = $(this).attr(opts.linkAttribute);
            if (url.length) window.location = url;
        });
    };

    _.extend(exports, {
      init: init
    });
})(go.components.tables = {});
