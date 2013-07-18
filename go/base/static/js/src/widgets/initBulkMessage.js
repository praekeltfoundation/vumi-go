$(function () {
    var $textarea = $('textarea[data-widget=bulkmessage]');
    $textarea.each(function(i, el) {
        new go.components.views.MessageTextView({el: el});
    });
});