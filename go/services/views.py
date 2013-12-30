from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from go.services import settings, get_service_view_definition


@login_required
def index(request):
    """Render the services index page"""
    return render(request, 'services/index.html', {
        'installed_services': settings.INSTALLED_SERVICES})


@login_required
def service(request, service_type, path_suffix=None):
    """Delegate request handling to the view definition of the given
    ``service_type``.
    """
    view_def = get_service_view_definition(service_type)
    view = view_def.get_view(path_suffix)
    return view(request)
