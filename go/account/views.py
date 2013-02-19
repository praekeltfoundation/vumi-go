from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.template.loader import render_to_string

from go.account.forms import EmailForm, AccountForm
from go.account.tasks import update_account_details
from go.base.token_manager import DjangoTokenManager
from vumi.persist.redis_manager import RedisManager


@login_required
def index(request):
    profile = request.user.get_profile()
    account = profile.get_user_account()
    account_form = AccountForm(request.user, initial={
        'name': request.user.first_name,
        'surname': request.user.last_name,
        'email_address': request.user.username,
        'msisdn': account.msisdn,
        'confirm_start_conversation': account.confirm_start_conversation,
    })
    email_form = EmailForm()

    if request.method == 'POST':
        if '_account' in request.POST:
            account_form = AccountForm(request.user, request.POST)
            if account_form.is_valid():

                data = account_form.cleaned_data
                params = {
                    'first_name': data['name'],
                    'last_name': data['surname'],
                    'new_password': data['new_password'],
                    'email_address': data['email_address'],
                    'msisdn': data['msisdn'],
                    'confirm_start_conversation':
                        data['confirm_start_conversation'],
                }

                site = Site.objects.get_current()
                redis = RedisManager.from_config(
                                    settings.VUMI_API_CONFIG['redis_manager'])
                token_manager = DjangoTokenManager(
                                    redis.sub_manager('token_manager'))

                token = token_manager.generate_task(request.path,
                    'Your details are being updated', update_account_details,
                    task_args=(request.user.id,),
                    task_kwargs=params, user_id=request.user.id,
                    immediate=True)

                token_url = 'http://%s%s' % (site.domain,
                                reverse('token', kwargs={'token': token}))

                context = params.copy()
                context.update({
                    'token_url': token_url,
                    })

                send_mail('Confirm account detail changes',
                    render_to_string('account/change_account_details_mail.txt',
                        context), settings.DEFAULT_FROM_EMAIL,
                        [request.user.email, 'support@vumi.org'])

                messages.info(request, 'Please confirm this change via email.')
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
