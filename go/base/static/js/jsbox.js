$(function() {
    // find the URL element;

    var $input = $('#id_jsbox-source_url');

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
                    cm.setValue(r);
                },
                error: function() {
                    alert('Something bad happened.');
                }

            })
        }
        return false;
    });
    $input.parent().append($button);
});