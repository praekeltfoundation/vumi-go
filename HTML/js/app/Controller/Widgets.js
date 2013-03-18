/*-----------------------------
Parse JSON Data into Widgets
-----------------------------*/
function InitWidgets(json){
	var stageMidPoint = (App.stage.rowHeight*App.stage.numRows)/2;
	//console.log('JSON Loaded: '+json);
	
	//--Get Widget Count
	var widgetLength = json.widgets.widget.length;
	//console.log(widgetLength+' number of Widgets');
	
	//--Define Starting Point
	//NO MORE STARTING POINT, WE USE WIDGET 1 INSTEAD
	/*
	var startWidget = '<div class="startWidget widget"></div>';
	$('.widgets').append(startWidget);
	$('.startWidget').css('top', gridSize + stageMidPoint - parseFloat($('.startWidget').css('height'))/2);
	$('.startWidget').css('left', gridSize/2 - parseFloat($('.startWidget').css('width'))/2);
	*/
	
	//--Parse JSON and Populate Widgets
	for(var i=0; i<widgetLength; i++){
		//Create Widget
		console.log(json.widgets.widget[i]);
		var widget = '<div class="widget smsWidget w'+i+'"></div>';
		$('.widgets').append(widget);
		
		//Position Widget
		$('.w'+i).css('top', gridSize + stageMidPoint - parseFloat($('.w'+i).css('height'))/2);
		$('.w'+i).css('left', gridSize/2 - parseFloat($('.w'+i).css('width'))/2 + (i+1)*320);
		
		//Make Draggable
		$('.w'+i).draggable({ opacity: 0.7, helper: "clone", revert: true});
		
		//Wire up plumbing
	}

};
