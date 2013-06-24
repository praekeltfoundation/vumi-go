from django import forms


class CampaignConfigurationForm(forms.Form):

    country = forms.ChoiceField(label="Select a destination",
                                          widget=forms.Select())
    # TODO: Channels are related to countries.
    channel = forms.ChoiceField(label="Select a channel",
                                         widget=forms.Select())
    keyword = forms.CharField(label="Define a keyword", max_length=100,
                              required=False)

    def __init__(self, user_api, *args, **kw):
        self.user_api = user_api
        super(CampaignConfigurationForm, self).__init__(*args, **kw)
        self.tagpool_set = self.user_api.tagpools()
        self.channel_options = self._load_channel_options()

        self.fields['country'].choices = [
            (country, country) for country in self.channel_options.keys()]
        channel_choices = []
        for country, channels in self.channel_options.iteritems():
            for name, items in channels.iteritems():
                channel_choices.append(['%s: %s' % (country, name[1]), items])
        self.fields['channel'].choices = channel_choices

    def _load_channel_options(self):
        channels = {}
        for pool in self.tagpool_set.pools():
            country_name = self.tagpool_set.country_name(pool, 'International')
            channel_options = channels.setdefault(country_name, {})
            display_name = self.tagpool_set.display_name(pool)
            channel_options[(pool, display_name)] = self._channel_options(pool)
        return channels

    def _channel_options(self, pool):
        if self.tagpool_set.user_selects_tag(pool):
            tag_options = [("%s:%s" % tag, tag[1]) for tag
                           in self.user_api.api.tpm.free_tags(pool)]
        else:
            tag_options = [("%s:" % pool,
                            "%s (auto)" % self.tagpool_set.display_name(pool))]
        return tag_options

    def tagpools_by_delivery_class(self):
        delivery_classes = {}
        for pool in self.tagpool_set.pools():
            delivery_class = self.tagpool_set.delivery_class(pool)
            if delivery_class is None:
                continue
            display_name = self.tagpool_set.display_name(pool)
            tag_pools = delivery_classes.setdefault(delivery_class, [])
            tag_pools.append((display_name, self.tag_options[pool]))
        return sorted(delivery_classes.items())

    def delivery_class_widgets(self):
        # Backported hack from Django 1.4 to allow me to iterate
        # over RadioInputs. Django 1.4 isn't happy yet with our nose tests
        # and twisted setup.
        field = self['delivery_class']
        for widget in field.field.widget.get_renderer(field.html_name,
                                                        field.value()):
            yield widget
