$(function () {
    var $textareas = $('textarea[data-widget=codemirror]');
    $textareas.each(function(i, el) {
        var cm = CodeMirror.fromTextArea(el, go.configs[$(el).attr('id')]);
        // This is invoked by another widget called `sourceUrl`        
        el.on_source_update = function(src) {
            cm.setValue(src);
        };
    });
});
