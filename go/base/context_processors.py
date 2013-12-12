from go.contacts import forms
from django.conf import settings


def standard_forms(request):
    if request.user.is_anonymous():
        return {}
    else:
        upload_contacts_form = forms.UploadContactsForm()
        new_contact_group_form = forms.ContactGroupForm()
        return {
            'upload_contacts_form': upload_contacts_form,
            'new_contact_group_form': new_contact_group_form,
        }


def credit(request):
    # TODO: Fill this in with real data.
    if request.user.is_authenticated() and hasattr(request, 'user_api'):
        return {
            'account_credits': 0,
        }
    return {}


def google_analytics(request):
    return {
        'google_analytics_ua': getattr(settings, "GOOGLE_ANALYTICS_UA", None),
    }
