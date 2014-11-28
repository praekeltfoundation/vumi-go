import os
from itertools import groupby

from django.conf import settings as go_settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.template import RequestContext, loader
from xhtml2pdf import pisa


from go.billing import settings
from go.billing.models import Statement


def sections_from_items(all_items):
    all_items = sorted(all_items, key=lambda d: d.channel)
    sections = groupby(all_items, lambda line: line.channel)

    sections = [{
        'name': channel,
        'items': list(sorted(items, key=lambda d: d.description))
    } for channel, items in sections]

    return sections


def billers_from_items(all_items):
    all_items = sorted(all_items, key=lambda d: d.billed_by)

    billers = [
        (name, list(items))
        for name, items in groupby(all_items, lambda line: line.billed_by)]

    billers = [{
        'name': billed_by,
        'channel_type': items[0].channel_type,
        'sections': sections_from_items(items)
    } for billed_by, items in billers]

    system_biller = next(
        (b for b in billers if b['name'] == settings.SYSTEM_BILLER_NAME),
        None)

    if system_biller is not None:
        billers.remove(system_biller)
        billers.append(system_biller)

    return billers


@login_required
def statement_view(request, statement_id=None):
    """Send a PDF version of the statement with the given
       ``statement_id`` to the user's browser.
    """
    statement = get_object_or_404(Statement, pk=statement_id)

    if not (request.user.is_staff or
            statement.account.user == request.user):
        raise Http404

    response = HttpResponse(mimetype='application/pdf')
    filename = "%s (%s).pdf" % (statement.title,
                                statement.from_date.strftime('%B %Y'))

    response['Content-Disposition'] = 'attachment; filename=%s' % (filename,)

    template = loader.get_template('billing/invoice.html')

    context = RequestContext(request, {
        'billers': billers_from_items(list(statement.lineitem_set.all()))
    })

    html_result = template.render(context)
    pisa.CreatePDF(html_result, dest=response, link_callback=link_callback)
    return response


# Convert HTML URIs to absolute system paths so xhtml2pdf can access those
# resources
def link_callback(uri, rel):
    # use short variable names
    static_url = go_settings.STATIC_URL
    static_root = go_settings.STATIC_ROOT
    media_url = go_settings.MEDIA_URL
    media_root = go_settings.MEDIA_ROOT

    # convert URIs to absolute system paths
    if uri.startswith(media_url):
        path = os.path.join(media_root, uri.replace(media_url, ""))
    elif uri.startswith(static_url):
        path = os.path.join(static_root, uri.replace(static_url, ""))

    # make sure that file exists
    if not os.path.isfile(path):
            raise Exception(
                'media URI must start with %s or %s' % (static_url, media_url))
    return path
