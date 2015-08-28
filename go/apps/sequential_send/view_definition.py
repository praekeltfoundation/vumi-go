from django import forms

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)


class ScheduleForm(forms.Form):

    RECURRING = (
        ('daily', 'Daily'),
        ('day_of_week', 'Day of Week'),
        ('day_of_month', 'Day of Month'),
        ('never', 'Never'),
    )

    recurring = forms.ChoiceField(
        choices=RECURRING,
        help_text="When messages should be sent.")

    days = forms.CharField(
        required=False,
        help_text="Which days of the week or month messages should be sent on."
                  " List of comma-separated numbers. Not required for daily"
                  " sends.")

    time = forms.CharField(
        help_text="Time at which messages should be sent, in 'HH:MM:SS'"
                  " format.")


class MessageForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea)


class BaseMessageFormSet(forms.formsets.BaseFormSet):
    @staticmethod
    def initial_from_config(data):
        return [{'message': message} for message in data]

    def to_config(self):
        return [form.cleaned_data['message'] for form in self
                if form.cleaned_data and not form.cleaned_data['DELETE']]


MessageFormSet = forms.formsets.formset_factory(
    MessageForm, can_delete=True, extra=1, formset=BaseMessageFormSet)


class EditSequentialSendView(EditConversationView):
    edit_forms = (
        ('schedule', ScheduleForm),
        ('messages', MessageFormSet),
    )


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditSequentialSendView
