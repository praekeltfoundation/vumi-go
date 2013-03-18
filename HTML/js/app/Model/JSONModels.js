/*-----------------------------
	Default JSON Load Error
-----------------------------*/
function errorLoadingJSON(){
	alert('Error loading JSON');
};

/*-----------------------------
	Initial JSON Loader
-----------------------------*/
function InitJSON(URI, successFn){
	//--Load Initial JSON data and store to App
	var jqxhr = $.getJSON(URI, function(json) {
		//For storage
		App.data = json;
	})
	.success(function() { successFn(App.data);})
	.error( function() { errorLoadingJSON(); });
};