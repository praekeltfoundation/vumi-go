$(function () {
    var $inputs = $('input[data-widget=sourceurl]');
    $inputs.each(function(i, el) {
        SourceUrl(el, go.configs[$(el).attr('id')]);
    });
});

function SourceUrl(el, dest_id) {
    var $input = $(el);
    var dest = $('#' + dest_id).get(0);

    var $button = $('<button class="btn btn-danger" type="button">' +
                    '<i class="icon-plus"></i> ' +
                    'Update from URL</button>');
    var $alert = $('<div></div>');

    $button.on('click', function() {
        var url = $input.val();
        if (url.length === 0) {
            SourceUrlAlert($alert, 'Source URL is required.');
        } else {
            // do the ajax, maybe show loading?
            $.ajax({
                url: '/cross-domain-xhr/',
                type: 'POST',
                data: {
                  url: url,
                  csrfmiddlewaretoken: $.cookie('csrftoken')
                },
                success: function(r) {
                    dest.on_source_update(r);
                    SourceUrlAlert($alert, 'Update successful.', 'success');
                },
                error: function(r) {
                    SourceUrlAlert($alert,
                                   'Could not load URL (' +
                                   r.status + ' ' + r.statusText + ').');
                }
            });
        }
        return false;
    });
    $input.wrap('<div class="input-append"></div>');
    $input.after($button);
    $input.addClass('span8');
    $input.parent().after($alert);
}

function SourceUrlAlert($alert, text, kind) {
    kind = (typeof kind == 'undefined') ? 'warning' : kind;
    $alert.html('<div class="alert alert-' + kind + '">' +
                '<a class="close" data-dismiss="alert">&times;</a>' +
                '<span>' + text + '</span>' +
                '</div>');
}
