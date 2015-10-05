(function(exports) {
  var DateRangeView = Backbone.View.extend({
    events: {
      'click .date-custom-toggle': function() {
        this.uncheckPresets();
        this.render();
        this.$customContainer().collapse('toggle');
      },
      'change .date-preset input': function() {
        this.render();
        this.$customContainer().collapse('hide');
      },
      'show.bs.collapse .date-custom-container': function() {
        this.setGlyph('up');
      },
      'hide.bs.collapse .date-custom-container': function() {
        this.setGlyph('down');
      }
    },
    initialize: function() {
      this.$customContainer().collapse({toggle: false});
    },
    $customToggleGlyph: function() {
      return this.$('.date-custom-toggle .glyphicon');
    },
    $customToggle: function() {
      return this.$('.date-custom-toggle');
    },
    $customContainer: function() {
      return this.$('.date-custom-container');
    },
    $presets: function() {
      return this.$('.date-preset');
    },
    $presetInputs: function() {
      return this.$('.date-preset input');
    },
    $checkedPreset: function() {
      return this.$('.date-preset input:checked').parent();
    },
    uncheckPresets: function(isCustom) {
      this.$presetInputs().prop('checked', false);
    },
    setGlyph: function(direction) {
      var $glyph = this.$customToggleGlyph();

      $glyph
        .removeClass($glyph.attr('data-up'))
        .removeClass($glyph.attr('data-down'))
        .addClass($glyph.attr(['data', direction].join('-')));
    },
    render: function() {
      var $checked = this.$checkedPreset();
      this.$presets().removeClass('active');
      this.$customToggle().removeClass('active');

      if ($checked.length) $checked.addClass('active');
      else this.$customToggle().addClass('active');

      this.trigger('rendered');
    }
  });

  _.extend(exports, {
    DateRangeView: DateRangeView
  });
})(go.components.dates = {});
