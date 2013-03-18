/*-----------------------------
		Global Variables
-----------------------------*/
var devMode = true;
var App = this;
var gridWidth = 350;
var gridHeight = 350;
var rows = 51;

$(document).ready(function(){
	
	/*------------------------------------------------
			Include External Scripts in DevMode
	Else load and minify all scripts in deferred order
	-------------------------------------------------*/
	if(devMode){
		
		//--Models
		$.getScript("js/app/Model/JSONModels.js");
		
		//--Views
		$.getScript("js/app/View/StageView.js");
		
		//--Controllers
		$.getScript("js/app/Controller/Widgets.js");
		
		//--Initialise App
		setTimeout(initApp,500)
	}else{
		//Load into Minify.js
		//------------here--------------//
	}
	
});

function initApp(){
	if(rows%2 === 0){
		console.log('Grid row count must be an odd number')
		return;
	};
	
	//--Initialize Stage
	App.stage = new Stage(rows, gridWidth, gridHeight);
	
	//--Load Initial JSON
	
	$('.widget').draggable({handle: ".sprite-ico-drag"});
	$('.selectpicker').selectpicker();
	//App.data = new InitJSON('js/data/Launch.json', InitWidgets);
};