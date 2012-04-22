/* Author: Praekelt */

$("#timepicker_1").timePicker({step:10, startTime:"00:00", endTime:"23:50", show24Hours: true,separator: ':',});
$('#conv-message').keyup(function(){
	    	$('#charcount').text($('#conv-message').val().length);
			if($('#conv-message').val().length>140){$('#valid-twitter').hide()}else{$('#valid-twitter').show()}
			if($('#conv-message').val().length>160){$('#valid-sms').hide()}else{$('#valid-sms').show()}
			$('span.preview-message').text($('#conv-message').val());
			
});

$('.typeahead').typeahead();

$(function() { $( "#datepicker" ).datepicker({ minDate: 0, dateFormat: 'dd MM yy' }); });
$(function() { $( "#dob" ).datepicker({ minDate: 0, dateFormat: 'dd MM yy' }); });

$('#surveyUSSD').click(function() {
	if($('#surveyUSSD').attr('checked')) { $('#surveyUSSDNum').show(); } else { $('#surveyUSSDNum').hide(); }
});

$('#search-filter-input').focus(function() {
	$('input#search-filter-input').val('');
});

$('#convtype').change(function() {
	var newAction = $('#convtype').val();
	$('#newConversationType').attr('action', newAction);
});