function SourceUrl(elem) {
    var $input = $('#' + elem.id);
    var $dest = null;  // TODO: find this somehow!?

    $button = $('<button><i class="icon-plus"></i> Update via URL</button>');
    $button.on('click', function() {
        var url = $input.val()
        if (url.length == 0) {
            alert('Source URL is required');
        } else {
            // do the ajax, maybe show loading?
            $.ajax('/app/jsbox/cross-domain-xhr/',  {
                type: 'POST',
                data: {'url': url},
                success: function(r) {
                    alert('Yay!');
                    // TODO: dest.on_source_update(r);
                },
                error: function() {
                    alert('Something bad happened.');
                }

            })
        }
        return false;
    });
    $input.parent().append($button);
}