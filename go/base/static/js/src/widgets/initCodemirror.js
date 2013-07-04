$(function () {
    var $textareas = $('textarea[data-widget=codemirror]');
    $textareas.each(function(i, el) {
        var cm = CodeMirror.fromTextArea(el, go.configs.codemirror[$(el).attr('id')]);
        
        el.on_source_update = function(src) {
            cm.setValue(src);
        };
    });
});
