/*-----------------------------
		Global Variables
-----------------------------*/


var conf = {
	colWidth: 450
	,rowHeight: 320
	,rows: 51
	,cols: 51
};

// Simple JavaScript Templating
// John Resig - http://ejohn.org/ - MIT Licensed
(function(){
  var cache = {};
 
  this.tmpl = function tmpl(str, data){
    // Figure out if we're getting a template, or if we need to
    // load the template - and be sure to cache the result.
    var fn = !/\W/.test(str) ?
      cache[str] = cache[str] ||
        tmpl(document.getElementById(str).innerHTML) :
     
      // Generate a reusable function that will serve as a template
      // generator (and which will be cached).
      new Function("obj",
        "var p=[],print=function(){p.push.apply(p,arguments);};" +
       
        // Introduce the data as local variables using with(){}
        "with(obj){p.push('" +
       
        // Convert the template into pure JavaScript
        str
          .replace(/[\r\t\n]/g, " ")
          .split("<%").join("\t")
          .replace(/((^|%>)[^\t]*)'/g, "$1\r")
          .replace(/\t=(.*?)%>/g, "',$1,'")
          .split("\t").join("');")
          .split("%>").join("p.push('")
          .split("\r").join("\\'")
      + "');}return p.join('');");
   
    // Provide some basic currying to the user
    return data ? fn( data ) : fn;
  };
})();


(function () {
	
	if (conf.rows%2 === 0 || conf.cols%2 === 0){
		throw new Error('Grid row/column count must be an odd number')
	};

	// Draw rows
	for(var i = 0, rowHTML = []; i < conf.rows; i++){
		rowHTML.push('<div class="hrow" style="height: '+conf.rowHeight+'px"></div>');
	};
	
	$('.rows').append(rowHTML.join(''));
	
	//Centre Stage Vertically
	//var headerHeight = parseFloat($('header').css('height'));
	$('.stage').css('top', (-conf.rows*conf.rowHeight)/2);
	
	
	//Resize Tool Canvas to height of Browser
	var resizeTool = function () {
		$('.tool').css('height', $(window).height() - $('.tool').position().top - 20);
	}
	$(window).resize(resizeTool);
	resizeTool();
	
	$('#overlay').hide();
	
	//Make Stage Draggable within Constraints
	var minX = -16000 + $(window).width(); // farthest to left it can go
	var maxX = 0; // farthest to right it can go
	var minY = (-conf.rows*conf.rowHeight) + $(window).height(); // set to your y position
	var maxY = 0; // set to your y position
	
	$('.stage').draggable({
		handle: '.rows, #overlay',
		containment: [minX,minY,maxX+20,maxY+150]
	});
	

	
	var Widget = function (data, x, y) {
		// Constructor
		data.editMode = false;
		
		this.obj = document.createElement("div");
		this.obj.className = "widget";
		this.obj.id = "widget_"+data.id;
		this.obj.innerHTML = tmpl("tmpl_widget", data);
		
		var stageMidPoint = (conf.rowHeight*conf.rows)/2;
		
		$('.widgets').append(this.obj);
		$(this.obj).css('top', stageMidPoint + conf.rowHeight*(y+1) - conf.rowHeight/2 - parseFloat($(this.obj).find(".header").css('height')));
		$(this.obj).css('left', conf.colWidth*(x+1) - conf.colWidth/2 - parseFloat($(this.obj).css('width'))/2);

		var that = this;
		
		// "Edit" button handler
		$(this.obj).find("button")[0].onclick = function () {
			data.editMode = true;
			var editBox = document.createElement("div");
			editBox.className = "widget Edit";
			editBox.id = "widget_edit_"+data.id;
			editBox.innerHTML = tmpl("tmpl_widget", data);
			
			$('.widgets').append(editBox);
			$(editBox).css('top', $(that.obj).position().top);
			$(editBox).css('left', $(that.obj).position().left);
			
			$('.selectpicker').selectpicker();
			$('#overlay').show();
			
			// "Save" button handler
			$(editBox).find("button")[0].onclick = function () {
				alert("TODO: prompt if any plumbing will be lost; update node; issue XHR");
				$(editBox).remove();
				$('#overlay').hide();
				
				// *UPDATE nodes object
			}
			// "Cancel" button handler
			$(editBox).find("button")[1].onclick = function () {
				// * CONFIRM modal dialog
				alert("TODO: prompt if any changes will be lost.");
				$(editBox).remove();
				$('#overlay').hide();
			}
			
			$(editBox).find(".sprite-ico-del").click(function () {
				alert("TODO: confirm delete; unhook node");
			});

			var btnAddOption = $(editBox).find(".widget-inner form button")[1];
			console.log(btnAddOption);
			if (btnAddOption) {
				btnAddOption.onclick = function () {
					alert("TODO: add row; add delete sprite.");
				}
			}
		}
		
		$(this.obj).find(".sprite-ico-del").click(function () {
			alert("TODO: confirm delete; unhook node");
		});
		
	};


	var plumbing = {
		init : function() {
				
			jsPlumb.importDefaults({
				// default drag options
				DragOptions : { cursor: 'pointer', zIndex:2000 },
				// default to blue at one end and green at the other
				EndpointStyles : [{ fillStyle:'#225588' }, { fillStyle:'#558822' }],
				// blue endpoints 7 px; green endpoints 11.
				Endpoints : [ [ "Dot", {radius:7} ], [ "Dot", { radius:11 } ]],
				// the overlays to decorate each connection with.  note that the label overlay uses a function to generate the label text; in this
				// case it returns the 'labelText' member that we set on each connection in the 'init' method below.
				ConnectionOverlays : [
					//[ "Arrow", { location: 0, foldback: 1, width: 20, length: 10 } ]
				],
				Container: $("#connections"),
				ConnectorZIndex:5
			});			

			// this is the paint style for the connecting lines..
			var connectorPaintStyle = {
				lineWidth:5,
				strokeStyle:"lightblue",
				joinstyle: "round",
				outlineColor:"white",
				outlineWidth: 0
			},
			
			// .. and this is the hover style. 
			connectorHoverStyle = {
				lineWidth: 5,
				strokeStyle:"black",
				connectorZIndex: 9
			},
			
			// the definition of source endpoints (the small blue ones)
			sourceEndpoint = {
				endpoint: "Rectangle",
				deleteEndpointsOnDetach:false,
				paintStyle:{ fillStyle:"transparent",radius: 4 },
				isSource:true,
				connector:[ "Flowchart", { stub:[20, 20], gap: 5 } ],								
				connectorStyle:connectorPaintStyle,
				hoverPaintStyle:connectorHoverStyle,
				connectorHoverStyle:connectorHoverStyle,
                dragOptions:{},
                overlays:[],
				anchor: [1, 0, 1, 0, 0, 17]
			},
			
			// a source endpoint that sits at BottomCenter
			//	bottomSource = jsPlumb.extend( { anchor:"BottomCenter" }, sourceEndpoint),
			// the definition of target endpoints (will appear when the user drags a connection) 
			targetEndpoint = {
				isTarget:true, 
				uniqueEndpoint:true,
				deleteEndpointsOnDetach:false,
				endpoint:"Dot",					
				paintStyle:{ fillStyle:"transparent",radius: 8 },
				hoverPaintStyle:connectorHoverStyle,
				maxConnections:-1,
				dropOptions:{ hoverClass:"hover", activeClass:"active" },
				isTarget:true,			
                overlays:[],
				connector:[ "Flowchart", { stub:[20, 20], gap: 5 } ],	
				anchor: [0, 0, -1, 0, 0, 37]		// y offset 38, i.e. at bottom of header
			};

			// listen for new connections
			jsPlumb.bind("jsPlumbConnection", function(connInfo, originalEvent) { 
				console.log(connInfo);
				// ** PREVENT LOOPS
				
				//connInfo.connection.getOverlay("label").setLabel(connection.sourceId.substring(6) + "-" + connection.targetId.substring(6));
			});
			
			
			this.source = function (el) {
				jsPlumb.makeSource(el, sourceEndpoint);
				return el;
			}
			this.target = function (el) {
				jsPlumb.makeTarget(el, targetEndpoint);
				return el;
			}
			this.connect = function (els, elt) {
				jsPlumb.connect({source: els, target: elt});
			}
			
			//
			// listen for clicks on connections, and offer to delete connections on click.
			//
			jsPlumb.bind("click", function(conn, originalEvent) {
				if (confirm("Delete connection from " + conn.sourceId + " to " + conn.targetId + "?"))
					jsPlumb.detach(conn); 
			});	
			
			jsPlumb.bind("connectionDrag", function(connection) {
				console.log("connection " + connection.id + " is being dragged");
			});		
			
			jsPlumb.bind("connectionDragStop", function(connection) {
				console.log("connection " + connection.id + " was dragged");
			});
		}
	};	

	

	$.getJSON('../../js/data/example.json', function(JSO) {	
		var nodes = JSO.nodes;

		// Parse nodes and generate widget objects in DOM
		for (var i = 0; i < nodes.length; i++) {
			var data = nodes[i];
			nodes[i].obj = new Widget(data, data.position[0], data.position[1]).obj;
		}

		
		jsPlumb.ready(function () {
			plumbing.init();
			
			// Create source and target endpoints for plumbing
			var t = [], s = [];
			for (var i = 0; i < nodes.length; i++) {
				t[i] = {};
				t[i].t = plumbing.target(nodes[i].obj);
				if (nodes[i].tails) {
					t[i].s = [];
					for (var k = 0; k < nodes[i].tails.length; k++) {
						t[i].s[k] = plumbing.source($(nodes[i].obj).find("li")[k]);
					}
				}

			}
			
			// Create connections between endpoints
			for (var i = 0; i < nodes.length; i++) {
				if (t[i].s) {
					for (var k = 0; k < t[i].s.length; k++) {
						plumbing.connect(t[i].s[k], "widget_"+nodes[i].tails[k].node_id);			// Note first param is object reference, second is selector! 
					}
				}
			}

			// Make all the widgets draggable
			jsPlumb.draggable(jsPlumb.getSelector(".widget"), { opacity: 0.7, helper: "clone", /*grid: [ conf.colWidth, conf.rowHeight ],*/ handle: ".header", revert: false});
		});			
	})
	.error(function() {
		// Deal with errors
		alert('Error loading JSON');
	});


	
})();




