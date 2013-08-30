from django.conf.urls.defaults import patterns, include, url
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.forms.models import modelformset_factory
from django.utils.translation import ugettext_lazy as _
from django.contrib import admin
from django.contrib import messages

from go.billing.models import TagPool, BaseCost, Account, CostOverride, \
    Transaction

from go.billing.forms import CreditLoadForm, BaseCreditLoadFormSet


class TagPoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')


class BaseCostAdmin(admin.ModelAdmin):
    list_display = ('tag_pool', 'message_direction', 'message_cost',
                    'markup_percent')

    search_fields = ('tag_pool__name',)
    list_filter = ('tag_pool', 'message_direction')


class ItemInline(admin.TabularInline):
    model = CostOverride
    extra = 1


class AccountAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'user', 'description',
                    'credit_balance')

    search_fields = ('account_number', 'user__email', 'description')
    readonly_fields = ('credit_balance',)
    inlines = (ItemInline,)
    actions = ['load_credits']

    def load_credits(self, request, queryset):
        selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
        redirect_url = "credits/load/?ids=%s" % (",".join(selected))
        return HttpResponseRedirect(redirect_url)
    load_credits.short_description = "Load credits for selected accounts"

    def get_urls(self):
        urls = super(AccountAdmin, self).get_urls()
        extra_urls = patterns(
            '', (r'^credits/load/$', self.credits_load))
        return extra_urls + urls

    def credits_load(self, request):
        """Load credits in the selected accounts"""
        queryset = Account.objects.filter(
            pk__in=request.GET.getlist('ids'))

        CreditLoadFormSet = modelformset_factory(
            Account, form=CreditLoadForm, formset=BaseCreditLoadFormSet,
            fields=('account_number',), extra=0)

        if request.method == 'POST':
            formset = CreditLoadFormSet(request.POST, queryset=queryset)
            if formset.is_valid():
                for form in formset:
                    form.load_credits()
                messages.info(request, _("Credits loaded successfully."))
                return HttpResponseRedirect('../../')
        else:
            formset = CreditLoadFormSet(queryset=queryset)

        opts = self.model._meta
        context = {
            'is_popup': "_popup" in request.REQUEST,
            'add': False,
            'change': False,
            'has_add_permission': False,
            'has_change_permission': False,
            'has_delete_permission': False,
            'opts': opts,
            'app_label': opts.app_label,
            'save_as': self.save_as,
            'save_on_top': self.save_on_top,
            'formset': formset,
            'errors': formset.errors
        }
        form_template = 'admin/billing/account/credit_load_form.html'
        return TemplateResponse(request, form_template, context,
                                current_app=self.admin_site.name)

    def has_delete_permission(self, request, *args, **kwargs):
        return False


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'account_number', 'tag_pool_name',
                    'message_direction', 'message_cost', 'markup_percent',
                    'credit_factor', 'credit_amount', 'status', 'created',
                    'last_modified')

    search_fields = ('account__account_number', 'tag_pool_name')
    list_filter = ('message_direction', 'status', 'created', 'last_modified')
    readonly_fields = ('account_number', 'tag_pool_name', 'message_direction',
                       'message_cost', 'markup_percent', 'credit_factor',
                       'credit_amount', 'status', 'created', 'last_modified')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, *args, **kwargs):
        return False


admin.site.register(TagPool, TagPoolAdmin)
admin.site.register(BaseCost, BaseCostAdmin)
admin.site.register(Account, AccountAdmin)
admin.site.register(Transaction, TransactionAdmin)
