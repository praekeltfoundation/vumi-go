$(function () {

    var $textareas = $('textarea[data-widget=codemirror]');

    $textareas.each(function(i, el) {
        var cm = CodeMirror.fromTextArea(el, codemirrorConfig[$(el).attr('id')]);
        // TODO: figure out where this comes from?
        el.on_source_update = function(src) {
            cm.setValue(src);
        }
    });
});