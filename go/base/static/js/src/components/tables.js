// go.components.tables
// ========================
// Tables that are used to manage swaths of data.

(function(exports) {
  var ViewCollection = go.components.structures.ViewCollection;

  // TODO Replace with TableView once our communication with the server is more
  // api-like
  var TableFormView = Backbone.View.extend({
    defaults: {
      rowLinkAttribute: 'data-url',
      actionPrefix: '_'
    },

    templates: {
      singular: _.template(
        "Are you sure you want to <%=action%> this item?"),
      plural: _.template(
        "Are you sure you want to <%=action%> these <%=numChecked%> items?"),
    },

    initialize: function() {
      // the table is rendered elsewhere, so el is an absolute
      // requirements.
      if (!this.$el.is('form')) {
        throw("TableFormView must get an `el` attribute that's a FORM element");
      }

      _(this.options).defaults(this.defaults);
      this._initActions();
    },

    _initActions: function() {
      this.$actions = $(this.options.actions);

      var self = this;
      this.$actions.each(function() {
        var $el = $(this),
            action = $el.attr('data-action'),
            modal = $el.attr('data-target');

        if (modal) {
          // If the action is targeting a modal, we rewire the modal's form to
          // submit the action instead
          $(modal).find('form').submit(function(e) {
            e.preventDefault();
            self.submitAction(action);
          });
        } else {
          // Otherwise, if the action doesn't target any modal, we show our own
          // modal with a confirmation message
          $el.click(function() { self.confirmAction(action); });
        }
      });
    },

    $headActionMarker: function() {
      return this.$('th:first-child input');
    },

    $actionMarkers: function() {
      return this.$('td:first-child input');
    },

    allChecked: function() {
      return !this.$('td:first-child input:not(:checked)').length;
    },

    numChecked: function() {
      return this.$('td:first-child input:checked').length;
    },

    refreshButtons: function() {
      this.$actions.prop('disabled', !this.numChecked());
    },

    submitAction: function(action) {
        // add an action field to the form; the view to which this
      // submits can use this field to determine which action
      // was invoked.
      var $input = $('<input>')
        .attr('type', 'hidden')
        .attr('name', this.options.actionPrefix + action)
        .appendTo(this.$el);

      this.$el.submit();
      $input.remove();

      return this;
    },

    confirmAction: function(action) {
      var numChecked = this.numChecked();

      var template = numChecked > 1
        ? this.templates.plural
        : this.templates.singular;

      var message = template({
        action: action,
        numChecked: numChecked
      });

      bootbox.confirm(message, function(submit) {
        if (submit) { this.submitAction(action); }
      }.bind(this));

      return this;
    },

    events: {
      // select or deselect all the checkboxes based on the state of the 
      // single checkbox in the header.
      'change th:first-child input': function(e) {
        var checked = this.$headActionMarker().is(':checked');

        this.$actionMarkers().each(function() {
          $(this).prop('checked', checked);
        });

        this.refreshButtons();
      },

      'change td:first-child input': function(e) {
        this.$headActionMarker().prop('checked', this.allChecked());
        this.refreshButtons();
      },

      // the `td` that houses the checkbox is clickable, this make the
      // checkbox easier to click because it increases the target
      // area.
      'click td:first-child': function(e) {
        $(e.target).find('input')
          .prop('checked', true)
          .change();
      },

      'click tbody tr td': function(e) {
        var $el = $(e.target).parents('tr'),
            url = $el.attr(this.options.rowLinkAttribute);

        // Follow the link associated with the row
        if (typeof url !== 'undefined') { window.location = url; }
      },

      'click tbody tr td *': function(e) {
        // Prevent the column's click events from propagating to its elements
        e.stopPropagation();
      }
    }
  });

  var RowView = Backbone.View.extend({
    tagName: 'tr',

    matches: function(query) {
      return _(query || {}).every(function(patterns, attrName) {
        var attr = this.model.get(attrName),
            i = patterns.length;

        while (i--) {
          if (attr.match(patterns[i])) { return true; }
        }

        return false;
      }, this);
    }
  });

  var RowCollection = ViewCollection.extend({
    type: RowView,

    parseQuery: function(query) {
      var parsed = {};

      _(query || {}).each(function(pattern, attrName) {
        if (_.isRegExp(pattern)) { parsed[attrName] = [pattern]; }
        else { parsed[attrName] = pattern.split(' '); }
      });

      return parsed;
    },

    matching: function(query) {
      query = this.parseQuery(query);

      return _.isEmpty(query)
        ? this.values()
        : this.where(function(r) { return r.matches(query); });
    }
  });

  var TableView = Backbone.View.extend({
    tagName: 'table',
    rowType: RowView,
    rowCollectionType: RowCollection,
    columnTitles: [],
    async: true,
    fadeDuration: 200,

    initialize: function(options) {
      if (options.async) { this.async = options.async; }
      if (options.rowType) { this.rowType = options.rowType; }
      if (options.columnTitles) { this.columnTitles = options.columnTitles; }

      if (options.rowCollectionType) {
        this.rowCollectionType = options.rowCollectionType;
      }

      this.models = options.models;
      this.rows = new this.rowCollectionType({
        models: this.models,
        type: this.rowType
      });

      this.initHead();
      this.initLoading();
      this.$body = $('<tbody>').appendTo(this.$el);
    },

    initHead: function() {
      if (!this.columnTitles.length) { return; }
      this.$head = $('<thead>').appendTo(this.$el);

      var $tr = $('<tr>').appendTo(this.$head);
      this.columnTitles.forEach(function(title) {
        $tr.append($('<th>').text(title));
      });
    },

    initLoading: function() {
      if (!this.async) { return; }

      this.$loading = $('<tbody>')
        .append($('<tr>')
          .append($('<td>')
            .attr('colspan', '0')
            .append($('<img>')
              .attr('src', go.urls.loading))));
    },

    fadeOut: function() {
      var d = $.Deferred();
      this.$el.fadeOut(this.fadeDuration, function() { d.resolve(); });
      return d.promise();
    },

    fadeIn: function() {
      var d = $.Deferred();
      this.$el.fadeIn(this.fadeDuration, function() { d.resolve(); });
      return d.promise();
    },

    renderBody: function(query) {
      this.$body.children().detach();
      this.$body.detach();

      this.rows
        .matching(query)
        .forEach(function(row) {
          row.render();
          this.$body.append(row.$el);
        }, this);

      return this;
    },

    render: function(query) {
      var self = this;

      return this
        .fadeOut()
        .then(function() {
          var d = $.Deferred(),
              p = d.promise();

          if (self.async) {
            // if the table is async, defer the row rendering until the call
            // stack has cleared, show a loading indicator and fade it out
            // once the row rendering is resolved
            _.defer(function() {
              self.renderBody(query);
              d.resolve();
            });

            self.$el.append(self.$loading);

            p = p
              .then(self.fadeOut.bind(self))
              .then(function() { self.$loading.detach(); });
          } else {
            // if the table is not async, render and resolve the deferred
            // immediately to prevent async behaviour
            self.renderBody(query);
            d.resolve();
          }

          return p;
        })
        .then(function() {
          self.$el.append(self.$body);
          return self.fadeIn();
        });
    }
  });

  _.extend(exports, {
    TableFormView: TableFormView,
    RowView: RowView,
    RowCollection: RowCollection,
    TableView: TableView
  });
})(go.components.tables = {});
