from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from go.account.forms import EmailForm


@login_required
def index(request):
    if request.method == 'POST':
        form = EmailForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            _from = request.user.email
            send_mail(subject, message, _from, ['support@vumi.org'])
            messages.info(request, 'Thanks for your email. We will be in '
                                    'touch shortly.')
            return redirect(reverse('account:index'))
    else:
        form = EmailForm()
    return render(request, 'account/index.html', {
        'form': form,
    })
