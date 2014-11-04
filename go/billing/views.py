import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template import RequestContext, loader
from xhtml2pdf import pisa


from go.billing.models import Statement


@login_required
def statement_view(request, statement_id=None):
    """Send a PDF version of the statement with the given
       ``statement_id`` to the user's browser.
    """
    statement = get_object_or_404(
        Statement, pk=statement_id, account__user=request.user)

    response = HttpResponse(mimetype='application/pdf')
    filename = "%s (%s).pdf" % (statement.title,
                                statement.from_date.strftime('%B %Y'))

    response['Content-Disposition'] = 'attachment; filename=%s' % (filename,)

    template = loader.get_template('billing/invoice.html')
    line_item_list = statement.lineitem_set.all()
    context = RequestContext(request, {'item_list': line_item_list})
    html_result = template.render(context)

    pisa.CreatePDF(html_result, dest=response, link_callback=link_callback)

    return response


# Convert HTML URIs to absolute system paths so xhtml2pdf can access those
# resources
def link_callback(uri, rel):
    # use short variable names
    static_url = settings.STATIC_URL
    static_root = settings.STATIC_ROOT
    media_url = settings.MEDIA_URL
    media_root = settings.MEDIA_ROOT

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
