from django import forms

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)


class ScheduleForm(forms.Form):
    recurring = forms.CharField(
        help_text="Currently supports 'daily' or 'day_of_month'.")
    days = forms.CharField(required=False,
        help_text="Required for 'day_of_month', comma-separated numbers.")
    time = forms.CharField(help_text="Time in 'HH:MM:SS' format.")


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
