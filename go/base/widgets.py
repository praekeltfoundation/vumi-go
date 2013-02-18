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

    def render(self, name, value, attrs=None):
        output = [super(CodeMirrorTextarea, self).render(name, value, attrs),
                  '<script type="text/javascript">'
                  'CodeMirror.fromTextArea(document.getElementById("%s"), %s);'
                  '</script>' %
                  ('id_%s' % name, self.option_json)]
        return mark_safe("\n".join(output))
