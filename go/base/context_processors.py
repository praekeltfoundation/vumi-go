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
    if request.user.is_authenticated() and hasattr(request, 'user_api'):
        profile = request.user.get_profile()
        api = request.user_api.api
        return {
            'account_credits': api.cm.get_credit(profile.user_account) or 0,
        }
    return {}


def google_analytics(request):
    return {
        'google_analytics_ua': getattr(settings, "GOOGLE_ANALYTICS_UA", None),
    }
