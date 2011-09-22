from go.contacts import forms


def user_profile(request):
    if request.user.is_anonymous():
        return {}
    return {
        'user_profile': request.user.get_profile()
    }

def standard_forms(request):
    if request.user.is_anonymous():
        return {}
    else:
        upload_contacts_form = forms.UploadContactsForm()
        new_contact_group_form = forms.NewContactGroupForm()

        user = request.user
        queryset = user.contactgroup_set.all()

        select_contact_group_form = forms.SelectContactGroupForm()
        select_contact_group_form['contact_group'].queryset = queryset

        return {
            'upload_contacts_form': upload_contacts_form,
            'new_contact_group_form': new_contact_group_form,
            'select_contact_group_form': select_contact_group_form,
        }

    