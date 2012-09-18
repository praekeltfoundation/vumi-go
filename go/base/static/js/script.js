/* Author: Praekelt */

$("#id_start_time").timePicker({step:10, startTime:"00:00", endTime:"23:50", show24Hours: true,separator: ':',});
$('#id_message').keyup(function(){
	    	$('#charcount').text($('#id_message').val().length);
			if($('#id_message').val().length>140){$('#valid-twitter').hide()}else{$('#valid-twitter').show()}
			if($('#id_message').val().length>160){$('#valid-sms').hide()}else{$('#valid-sms').show()}
			$('span.preview-message').text($('#id_message').val());
			
});

$('.typeahead').typeahead();

$(function() { $( "#id_start_date" ).datepicker({ minDate: 0, dateFormat: 'yy-mm-dd' }); });
$(function() { $( "#dob" ).datepicker({ minDate: 0, dateFormat: 'yy-mm-dd' }); });

$('#surveyUSSD').click(function() {
	if($('#surveyUSSD').attr('checked')) { $('#surveyUSSDNum').show(); } else { $('#surveyUSSDNum').hide(); }
});

$('#convtype').change(function() {
	var newAction = $('#convtype').val();
	$('#newConversationType').attr('action', newAction);
});

/* show or hide the tag pool options depending on the delivery class chosen */
$('.delivery-class-radio').change(function() {
    delivery_classes = $('.delivery-class-radio[name=delivery_class]');
    delivery_classes.each(function(index, element) {
        var deliveryClass = $(element);
        var tagPoolDiv = $('#' + deliveryClass.val() + '_tag_pool_selection');
        var selectField = $('#' + deliveryClass.val() + '_tag_pool_selection select');
        if($(deliveryClass).attr('checked')) {
            tagPoolDiv.show();
            selectField.removeAttr('disabled');
        } else {
            tagPoolDiv.hide();
            selectField.attr('disabled', 'disabled');
        }
    });

})