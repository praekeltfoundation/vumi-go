function Stage(numRows, rowHeight, colWidth){
	//Initialize Rows
	initRows(numRows, rowHeight);
	
	//Make Stage Draggable within Constraints
	var minX = -16000 + $(window).width(); // farthest to left it can go
  	var maxX = 0; // farthest to right it can go
	var minY = (-numRows*rowHeight) + $(window).height(); // set to your y position
	var maxY = 0; // set to your y position
	
	
	$('.stage').draggable({
		handle: '.rows',
		containment: [minX,minY,maxX+20,maxY+150]
	});
	
	
	//---Getters and Setters
	this.numRows = numRows;
	this.rowHeight = rowHeight;
	this.colWidth = colWidth;
	
};

function initRows(count, rowHeight){
	
	
	for(var i=0; i<count; i++){
		//Define Row
		var row;
		if(devMode){
			row = '<div class="hrow"></div>';
		}else{
			row = '<div class="stageRow"></div>';
		}
		
		//Append rows to stage
		$('.rows').append(row);
	};
	
	//Centre Stage Vertically
	var headerHeight = parseFloat($('header').css('height'));
	$('.stage').css('top', (-rowHeight*count)/2 + headerHeight/2);
	
	//Resize Tool Canvas to height of Browser
	$('.tool').css('height', $(window).height());
};