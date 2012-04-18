/* Author: Praekelt */

$("#ctime").timePicker({step:10, startTime:"00:00", endTime:"23:50", show24Hours: true,separator: ':',});
$('#cmessage').keyup(function(){
	    	$('#charcount').text($('#cmessage').val().length);
			if($('#cmessage').val().length>140){$('#valid-twitter').hide()}else{$('#valid-twitter').show()}
			if($('#cmessage').val().length>160){$('#valid-sms').hide()}else{$('#valid-sms').show()}
			$('span.preview-message').text($('#cmessage').val());
			
});

$('.typeahead').typeahead();
$(function() { $( "#cdate" ).datepicker({ minDate: 0, dateFormat: 'dd MM yy' }); });
$(function() { $( "#dob" ).datepicker({ minDate: 0, dateFormat: 'dd MM yy' }); });

$('#surveyUSSD').click(function() {
	if($('#surveyUSSD').attr('checked')) { $('#surveyUSSDNum').show(); } else { $('#surveyUSSDNum').hide(); }
});