from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from go.account.forms import EmailForm, AccountForm


@login_required
def index(request):
    profile = request.user.get_profile()
    account_form = AccountForm(request.user, initial={
        'name': request.user.first_name,
        'surname': request.user.last_name,
        'email_address': request.user.username,
        'msisdn': profile.msisdn,
        'confirm_start_conversation': profile.confirm_start_conversation,
    })
    email_form = EmailForm()

    if request.method == 'POST':
        if '_account' in request.POST:
            account_form = AccountForm(request.user, request.POST)
            if account_form.is_valid():
                user = request.user
                new_password = account_form.cleaned_data['new_password']
                if new_password:
                    user.set_password(new_password)
                user.first_name = account_form.cleaned_data['name']
                user.last_name = account_form.cleaned_data['surname']
                email_address = account_form.cleaned_data['email_address']
                user.email = user.username = email_address
                user.save()

                profile = user.get_profile()

                profile.msisdn = account_form.cleaned_data['msisdn']
                profile.confirm_start_conversation = account_form.cleaned_data[
                                                'confirm_start_conversation']
                profile.save()

                messages.info(request, 'Account Details updated.')
                return redirect('account:index')

        elif '_email' in request.POST:
            email_form = EmailForm(request.POST)
            if email_form.is_valid():
                subject = email_form.cleaned_data['subject']
                message = email_form.cleaned_data['message']
                _from = request.user.email
                send_mail(subject, message, _from, ['support@vumi.org'])
                messages.info(request, 'Thanks for your email. We will be in '
                                        'touch shortly.')
                return redirect(reverse('account:index'))
            else:
                messages.error(request, 'We didn\'t understand some of the '
                    'values your provided in the email form, please try '
                    'again.')
    return render(request, 'account/index.html', {
        'email_form': email_form,
        'account_form': account_form,
    })
