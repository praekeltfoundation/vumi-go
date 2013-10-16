$(function () {
    var $textareas = $('textarea[data-widget=codemirror]');
    $textareas.each(function() {
        var $el = $(this);
        var cm = CodeMirror.fromTextArea(this, go.configs[$el.attr('id')]);

        // This is invoked by another widget called `sourceUrl`        
        $el.on('source:update', function(e) {
            cm.setValue(e.src);
        });
    });
});
