$(function () {
    var $inputs = $('input[data-widget=sourceurl]');
    $inputs.each(function(i, el) {
        SourceUrl(el, go.configs[$(el).attr('id')]);
    });
});

function SourceUrl(el, dest_id) {
    var $target = $(el);

    var $dest = $('#' + dest_id);

    var $button = $('<button>')
        .addClass('btn btn-primary')
        .attr('type', 'button')
        .append($('<i>').addClass('glyphicon glyphicon-plus'))
        .append($('<span>').text(' Update from Url'));

    var $alert = $('<div>');

    var $input = $target
        .clone()
        .addClass('form-group');

    $target.replaceWith($('<div>')
        .addClass('form-group')
        .append($('<div>')
            .addClass('row')
            .append($('<div>')
                .addClass('col-md-8')
                .append($input))
            .append($('<div>')
                .addClass('col-md-4')
                .append($button)))
        .append($alert));

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
                    $dest.trigger($.Event('source:update', {src: r}));
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
}

function SourceUrlAlert($alert, text, kind) {
    kind = (typeof kind == 'undefined') ? 'warning' : kind;
    $alert.html('<div class="alert alert-' + kind + '">' +
                '<a class="close" data-dismiss="alert">&times;</a>' +
                '<span>' + text + '</span>' +
                '</div>');
}
