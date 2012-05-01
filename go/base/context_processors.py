from go.contacts import forms
from go.vumitools.contact import ContactStore


def user_profile(request):
    if request.user.is_anonymous():
        return {}
    return {
        'user_profile': request.user.get_profile(),
    }


def standard_forms(request):
    if request.user.is_anonymous():
        return {}
    else:
        upload_contacts_form = forms.UploadContactsForm()
        new_contact_group_form = forms.NewContactGroupForm()

        contact_store = ContactStore.from_django_user(request.user)
        select_contact_group_form = forms.SelectContactGroupForm(
            groups=contact_store.list_groups())

        return {
            'upload_contacts_form': upload_contacts_form,
            'new_contact_group_form': new_contact_group_form,
            'select_contact_group_form': select_contact_group_form,
        }


def credit(request):
    if request.user.is_authenticated() and hasattr(request, 'user_api'):
        profile = request.user.get_profile()
        api = request.user_api.api
        return {
            'account_credits': api.cm.get_credit(profile.user_account),
        }
    return {}
