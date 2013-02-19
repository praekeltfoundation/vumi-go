"""A widget for displaying code in a CodeMirror editor"""

import json

from django import forms
from django.utils.safestring import mark_safe


class CodeMirrorTextarea(forms.Textarea):
    """A textarea that is edited via the CodeMirror editor."""

    DEFAULT_CONFIG = {
        'lineNumbers': True,
    }

    def __init__(self, attrs=None, mode='javascript', theme='twilight',
                 config=None, codemirror_path='codemirror', **kwargs):
        super(CodeMirrorTextarea, self).__init__(attrs=attrs, **kwargs)

        if isinstance(mode, basestring):
            mode = {'name': mode}
        self.mode_name = mode['name']

        config = config if config is not None else self.DEFAULT_CONFIG
        config = config.copy()
        config['mode'] = mode
        config['theme'] = theme

        self.option_json = json.dumps(config)

        self.js_files = (
            "%s/lib/codemirror-compressed.js" % (codemirror_path,),
        )
        self.css_files = {
            'all': (
                "%s/lib/codemirror.css" % (codemirror_path,),
                "%s/theme/%s.css" % (codemirror_path, theme),
            ),
        }

    @property
    def media(self):
        return forms.Media(css=self.css_files, js=self.js_files)

    @staticmethod
    def id_for_name(name):
        return "id_%s" % (name,)

    def render(self, name, value, attrs=None):
        code_textarea_id = self.id_for_name(name)
        output = [super(CodeMirrorTextarea, self).render(name, value, attrs),
                  '<script type="text/javascript">'
                  '$(function () {'
                  '  var elem = document.getElementById("%s");'
                  '  var cm = CodeMirror.fromTextArea(elem, %s);'
                  '  elem.on_source_update = function (src) {'
                  '    cm.setValue(src);'
                  '  };'
                  '});'
                  '</script>' %
                  (code_textarea_id, self.option_json)]
        return mark_safe("\n".join(output))


class CodeField(forms.CharField):
    widget = CodeMirrorTextarea


class SourceUrlTextInput(forms.TextInput):
    """Source URL widget."""

    def __init__(self, code_field, attrs=None, **kwargs):
        super(SourceUrlTextInput, self).__init__(attrs=attrs, **kwargs)
        self.code_field = code_field

    @property
    def media(self):
        js = ('js/source_url.js',)
        return forms.Media(js=js)

    def code_field_name(self, name):
        parts = name.rsplit('-', 1)
        if len(parts) != 2:
            raise ValueError("Couldn't understand field name %r" % name)
        return "%s-%s" % (parts[0], self.code_field)

    def render(self, name, value, attrs=None):
        source_input_id = 'id_%s' % (name,)
        # constructing the correct code field name like this isn't
        # great but I don't have a better idea
        code_field_name = self.code_field_name(name)
        code_field_id = CodeMirrorTextarea.id_for_name(code_field_name)
        output = [super(SourceUrlTextInput, self).render(name, value, attrs),
                  '<script type="text/javascript">'
                  'SourceUrl(document.getElementById("%s"),'
                  '          document.getElementById("%s"));'
                  '</script>' %
                  (source_input_id, code_field_id)]
        return mark_safe("\n".join(output))


class SourceUrlField(forms.URLField):
    def __init__(self, code_field, **kwargs):
        widget = SourceUrlTextInput(code_field=code_field)
        super(SourceUrlField, self).__init__(widget=widget, **kwargs)
