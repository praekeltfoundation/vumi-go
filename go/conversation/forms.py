import datetime

from django import forms
from django.utils import timezone


class ConversationDetailForm(forms.Form):
    name = forms.CharField(label='Conversation name', max_length=100)
    description = forms.CharField(
        label="Conversation description", required=False)


class NewConversationForm(ConversationDetailForm):
    def __init__(self, user_api, *args, **kwargs):
        super(NewConversationForm, self).__init__(*args, **kwargs)
        apps = (v for k, v in sorted(user_api.applications().iteritems()))
        type_choices = [(app['namespace'], app['display_name'])
                        for app in apps]
        self.fields['conversation_type'] = forms.ChoiceField(
            label="Which kind of conversation would you like?",
            choices=type_choices)


class ConfirmConversationForm(forms.Form):
    token = forms.CharField(required=True, widget=forms.HiddenInput)


class ConversationSearchForm(forms.Form):
    query = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'input-xlarge',
        }))
    conversation_status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Status ...'),
            ('running', 'Running'),
            ('finished', 'Finished'),
            ('draft', 'Draft'),
        ],
        widget=forms.Select(attrs={'class': 'input-sm'}))

    def __init__(self, *args, **kw):
        conversation_types = kw.pop('conversation_types')
        super(ConversationSearchForm, self).__init__(*args, **kw)
        self.fields['conversation_type'] = forms.ChoiceField(
            required=False,
            choices=([('', 'Type ...')] + conversation_types),
            widget=forms.Select(attrs={'class': 'input-small'}))


class ReplyToMessageForm(forms.Form):
    in_reply_to = forms.CharField(widget=forms.HiddenInput, required=True)
    # NOTE: the to_addr is only used to display in the UI, when sending the
    #       reply the 'from_addr' of the 'in_reply_to' message copied over.
    to_addr = forms.CharField(label='Send To', required=True)
    content = forms.CharField(
        label='Reply Message',
        required=True,
        widget=forms.Textarea)


class MessageDownloadForm(forms.Form):

    CUSTOM_DATE_FORMAT = '%Y/%m/%d'

    _LOCALS = locals()

    format = forms.ChoiceField(
        required=True, initial='csv',
        choices=[
            ('csv', 'csv'), ('json', 'json'),
        ])

    direction = forms.ChoiceField(
        required=True, initial='inbound',
        choices=[
            ('inbound', 'inbound'), ('outbound', 'outbound'),
        ])

    _LOCALS['date-preset'] = forms.ChoiceField(
        required=False, initial='all',
        choices=[
            ('all', 'all'), ('1d', '1d'), ('7d', '7d'), ('30d', '30d'),
        ])

    _LOCALS['date-from'] = forms.DateField(
        required=False,
        input_formats=[CUSTOM_DATE_FORMAT])

    _LOCALS['date-to'] = forms.DateField(
        required=False,
        input_formats=[CUSTOM_DATE_FORMAT])

    def _parse_date_preset(self, preset):
        if preset == "all":
            return None, None
        days = int(preset[:-1])
        start_time = (
            datetime.datetime.utcnow() - datetime.timedelta(days=days))
        return start_time, None

    def _date_to_utc(self, custom_date):
        if custom_date is None:
            return None
        return datetime.datetime(
            custom_date.year, custom_date.month, custom_date.day,
            tzinfo=timezone.utc)

    def _format_custom_date_part(self, date, default):
        if date is None:
            return default
        return date.strftime('%Y%m%d')

    def _format_custom_date_filename(self, start_date, end_date):
        if start_date is None and end_date is None:
            return "all"
        return "-".join([
            self._format_custom_date_part(start_date, 'until'),
            self._format_custom_date_part(end_date, 'now'),
        ])

    def date_range(self):
        """Return the date range.

        :returns:
            A tuple of `start_date`, `end_date`, `filename_date`.
        """
        date_preset = self.cleaned_data.get('date-preset')
        if date_preset:
            start_date, end_date = self._parse_date_preset(date_preset)
            filename_date = date_preset
        else:
            start_date = self._date_to_utc(self.cleaned_data.get('date-from'))
            end_date = self._date_to_utc(self.cleaned_data.get('date-to'))
            filename_date = self._format_custom_date_filename(
                start_date, end_date)
        return start_date, end_date, filename_date
