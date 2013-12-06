from django.conf.urls.defaults import patterns, url

from go.vouchers import views

urlpatterns = patterns(
    '',
    url(r'^$', views.voucher_list, name='voucher_list'),
)
