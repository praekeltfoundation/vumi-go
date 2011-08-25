$(document).ready(function() {
	/*--HEADER SIGNIN FLYOUT --*/
	$('#top-nav-signin').click(function() {
		$('#signin').slideToggle();
	});
	$('.go-signin').click(function() {
		$('#signin').slideToggle();
	});
	$('#close-sign a').click(function() {
		$('#signin').slideUp();
		$('#forgot-form').hide();
		$('#signin-form').fadeIn('slow');
	});
	$('#forgot-click').click(function() {
		$('#signin-form').hide();
		$('#forgot-form').fadeIn();
	});
	$('#signin-return-click').click(function() {
		$('#forgot-form').hide();
		$('#signin-form').fadeIn();
	});
	$('#reset-again').click(function() {
		$('#signin').slideDown();
		$('#signin-form').hide();
		$('#forgot-form').fadeIn();
	});
	$('#password-clear').show();
	$('#password-password').hide();

	$('#password-clear').focus(function() {
   		$('#password-clear').hide();
    	$('#password-password').show();
    	$('#password-password').focus();
		$('#password-password').addClass('black');
	});
	$('#password-password').blur(function() {
    if($('#password-password').val() == '') {
        $('#password-clear').show();
        $('#password-password').hide();
		
    }
	$('#password-password').removeClass('black');
	});
	/* -- HOME FEATURES -- */
	$('#top-nav-features').click(function() {
		$('#more-features').slideDown();
		$('#features-learn-more').hide();
	});
	$('#feature-p').click(function() {
		$('#more-features').slideDown();
		$('#features-learn-more').hide();
	});
	
	$().ready(function() {
  		$('#feature1').jqm({ajax: 'http://prototypes.praekelt.co.za/vumi/web/feature.html', trigger: 'a.jqModal'});
	});
	/* -- FORM VALIDATIONS -- */
	$(function() {
		$('#signin-form').validate();
		$('#forgot-form').validate();
		$('#signup').validate();
		$("#set-new-password").validate({
		  rules: {
			password: "required",
			confirm: {
			  equalTo: "#new-input-password"
			}
		  }
		});
		
		
		
	});
	/* -- SIGNUP VALIDATIONS -- */
	
	//Error messages show/hide
	jQuery(function () {
		//quote message
		jQuery('form#signup input[name="submit"]').click(function() {
  			if(jQuery('form#signup').has('input.error, select.error, textarea.error')){
			$('h3#signup-heading').text("Oops. Pls check your details:");
			$('h3#signup-heading').css("color","#cc3333");
			} else {
			alert("noerrors");
			}
		});
		//turn labels red
		jQuery('form').submit(function() {
			//turn labels red
			jQuery('input.error, select.error, textarea.error').parent().find('label').addClass('errored');
		});
		//remove labels red
		jQuery('select, input, textarea').change(function() {
			if(jQuery(this).parent().find('select, input').has('.valid')){
				jQuery(this).parent().find('label').removeClass('errored');
			}
		});
	});
	
	$('input.txtbox').blur(function() {
		if ($(this).val() != '') {
			$(this).addClass('typed');
		}
		else {
			$(this).removeClass('typed');
		}
	});
	
	$('a.notice-close').click(function() {
		$(this).parent().slideUp();
	});
});