from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string

from registration.views import RegistrationView

from go.account.forms import (EmailForm, AccountForm, UserAccountForm,
    UserProfileForm, RegistrationForm)
from go.account.tasks import update_account_details
from go.base.models import UserProfile
from go.token.django_token_manager import DjangoTokenManager
from go.billing import settings as billing_settings
from go.billing.models import Statement


class GoRegistrationView(RegistrationView):
    """Go sub-class of django-registration's RegistrationView."""

    form_class = RegistrationForm


@login_required
def details(request):
    profile = request.user.get_profile()
    token_manager = DjangoTokenManager(request.user_api.api.token_manager)
    account = profile.get_user_account()
    account_form = AccountForm(request.user, initial={
        'name': request.user.first_name,
        'surname': request.user.last_name,
        'email_address': request.user.email,
        'msisdn': account.msisdn,
        'confirm_start_conversation': account.confirm_start_conversation,
        'email_summary': account.email_summary,
    })
    email_form = EmailForm()
    password_change_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        if '_account' in request.POST:
            account_form = AccountForm(request.user, request.POST)
            if account_form.is_valid():

                data = account_form.cleaned_data
                params = {
                    'first_name': data['name'],
                    'last_name': data['surname'],
                    'email_address': data['email_address'],
                    'msisdn': data['msisdn'],
                    'email_summary': data['email_summary'],
                    'confirm_start_conversation':
                        data['confirm_start_conversation'],
                }

                token = token_manager.generate_callback_token(request.path,
                    'Your details are being updated', update_account_details,
                    callback_args=(request.user.id,),
                    callback_kwargs=params, user_id=request.user.id)

                context = params.copy()
                context.update({
                    'token_url': token_manager.url_for_token(token),
                    })

                send_mail(
                    'Vumi Go account detail change confirmation',
                    render_to_string(
                        'account/change_account_details_mail.txt',
                        context),
                    settings.DEFAULT_FROM_EMAIL,
                    [request.user.email, 'support@vumi.org'])

                messages.info(request,
                    'Please confirm this change by clicking on the link '
                    'that was just sent to your mailbox.')
                return redirect('account:details')

        elif '_email' in request.POST:
            email_form = EmailForm(request.POST)
            if email_form.is_valid():
                subject = email_form.cleaned_data['subject']
                message = email_form.cleaned_data['message']
                _from = request.user.email
                send_mail(subject, message, _from, ['support@vumi.org'])
                messages.info(request, 'Thanks for your email. We will be in '
                                        'touch shortly.')
                return redirect(reverse('account:details'))
            else:
                messages.error(request, 'We didn\'t understand some of the '
                    'values your provided in the email form, please try '
                    'again.')

        elif '_password' in request.POST:
            password_change_form = PasswordChangeForm(request.user,
                                                      request.POST)
            if password_change_form.is_valid():
                password_change_form.save()

    return render(request, 'account/details.html', {
        'email_form': email_form,
        'account_form': account_form,
        'password_change_form': password_change_form,
        'account_key': request.user_api.user_account_key,
    })


@login_required
def user_list(request):
    """Fetch a list of users that belong to the same company in the
    users profile."""

    user_list = []
    user_profile = request.user.get_profile()
    if user_profile.organisation:
        for profile in UserProfile.objects.filter(
                organisation=user_profile.organisation):
            user_list.append(profile.user)

    return render(request, 'account/user_list.html', {
        'user_list': user_list,
        'is_admin': request.user.get_profile().is_admin
    })


@login_required
def user_detail(request, user_id=None):
    """Shows a form that allows you to edit the details of this user"""

    # Is the `user` an admin, do they have the rights to edit a user?
    user_profile = request.user.get_profile()
    if not user_profile.is_admin:
        return HttpResponseForbidden("You're not an admin.")

    # Are they editing a member of the same organisation?
    if user_id:
        # editing
        edit_user = get_object_or_404(User, id=user_id)
        edit_user_profile = edit_user.get_profile()
        if user_profile.organisation != edit_user_profile.organisation:
            return HttpResponseForbidden("This user is not in your \
                organisation.")
    else:
        # creating a new user
        edit_user = None
        edit_user_profile = UserProfile(
            organisation=user_profile.organisation)

    user_form = UserAccountForm(instance=edit_user)
    user_profile_form = UserProfileForm(instance=edit_user_profile,
            initial={
                'organisation': user_profile.organisation
            })

    if request.method == 'POST':
        user_form = UserAccountForm(request.POST, instance=edit_user)
        user_profile_form = UserProfileForm(request.POST,
                                            instance=edit_user_profile)

        if user_form.is_valid() and user_profile_form.is_valid():
            user_form.save()
            user_profile_form.save()
            messages.add_message(request, messages.INFO, 'User saved')

    return render(request, 'account/user_detail.html', {
        'edit_user': edit_user,
        'user_form': user_form,
        'user_profile_form': user_profile_form
    })


@login_required
def billing(request, template_name='account/billing.html'):
    """Display a list of available statements for the logged in user"""
    order_by = request.GET.get(
        'o', billing_settings.STATEMENTS_DEFAULT_ORDER_BY)

    # Validate the order_by parameter by making sure the field exists
    if order_by.startswith('-'):
        field = order_by[1:]
    else:
        field = order_by
    if field not in Statement._meta.get_all_field_names():
        order_by = billing_settings.STATEMENTS_DEFAULT_ORDER_BY

    # If the user has multiple accounts, take the first one
    account_list = request.user.account_set.all()
    if account_list:
        statement_list = Statement.objects\
            .filter(account=account_list[0])\
            .order_by(order_by)

    else:
        statement_list = []

    # Paginate statements
    paginator = Paginator(statement_list,
                          billing_settings.STATEMENTS_PER_PAGE)

    try:
        page = paginator.page(request.GET.get('p', 1))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    context = {
        'order_by': order_by,
        'paginator': paginator,
        'page': page,
    }
    return render(request, template_name, context)
