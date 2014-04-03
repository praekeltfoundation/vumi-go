from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect

from go.base.utils import get_service_view_definition, service_or_404
from go.service.forms import NewServiceComponentForm


SERVICE_COMPONENTS_PER_PAGE = 12


@login_required
def index(request):
    # grab the fields from the GET request
    user_api = request.user_api

    services = sorted(
        user_api.active_service_components(), key=lambda s: s.name)

    paginator = Paginator(services, SERVICE_COMPONENTS_PER_PAGE)
    try:
        page = paginator.page(request.GET.get('p', 1))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    return render(request, 'service/dashboard.html', {
        'services': services,
        'paginator': paginator,
        'pagination_params': '',
        'page': page,
    })


@login_required
def service(request, service_key, path_suffix):
    service = service_or_404(request.user_api, service_key)
    view_def = get_service_view_definition(
        service.service_component_type, service)
    view = view_def.get_view(path_suffix)
    return view(request, service)


@login_required
def new_service(request):
    if request.method == 'POST':
        form = NewServiceComponentForm(request.user_api, request.POST)
        if form.is_valid():
            service_type = form.cleaned_data['service_component_type']

            view_def = get_service_view_definition(service_type)
            service = request.user_api.new_service_component(
                service_type, name=form.cleaned_data['name'],
                description=form.cleaned_data['description'], config={},
            )
            messages.info(request, 'Service component created successfully.')

            view_def = get_service_view_definition(
                service.service_component_type, service)

            next_view = 'show'
            if view_def.is_editable:
                next_view = 'edit'

            return redirect(view_def.get_view_url(
                next_view, service_key=service.key))
    else:
        form = NewServiceComponentForm(request.user_api)
    return render(request, 'router/new.html', {
        'router_form': form,
    })
