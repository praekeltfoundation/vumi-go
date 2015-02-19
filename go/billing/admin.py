from django.core import urlresolvers
from django.conf.urls import patterns
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.forms.models import modelformset_factory
from django.utils.translation import ugettext_lazy as _
from django.utils.html import format_html
from django.contrib import admin
from django.contrib import messages

from go.billing.models import (
    TagPool, Account, MessageCost, Transaction, Statement, LineItem,
    LowCreditNotification, TransactionArchive)
from go.billing.forms import (
    CreditLoadForm, BaseCreditLoadFormSet, MessageCostForm, TagPoolForm)


class TagPoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')
    form = TagPoolForm


class AccountAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'user', 'description',
                    'credit_balance', 'last_topup_balance')

    search_fields = ('account_number', 'user__email', 'description')
    readonly_fields = ('credit_balance',)
    actions = ['load_credits']

    def load_credits(self, request, queryset):
        selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
        request.session['account_ids'] = selected
        redirect_url = "credits/load/"
        return HttpResponseRedirect(redirect_url)
    load_credits.short_description = "Load credits for selected accounts"

    def get_urls(self):
        urls = super(AccountAdmin, self).get_urls()
        extra_urls = patterns(
            '', (r'^credits/load/$', self.credits_load))
        return extra_urls + urls

    def credits_load(self, request):
        """Load credits in the selected accounts"""
        account_ids = request.session.get('account_ids', [])
        queryset = Account.objects.filter(pk__in=account_ids)
        CreditLoadFormSet = modelformset_factory(
            Account, form=CreditLoadForm, formset=BaseCreditLoadFormSet,
            fields=('account_number',), extra=0)

        if request.method == 'POST':
            formset = CreditLoadFormSet(request.POST, queryset=queryset)
            if formset.is_valid():
                for form in formset:
                    form.load_credits()
                del request.session['account_ids']
                messages.info(request, _("Credits loaded successfully."))
                changelist_url = urlresolvers.reverse(
                    'admin:billing_account_changelist')

                return HttpResponseRedirect(changelist_url)
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


class MessageCostAdmin(admin.ModelAdmin):
    list_display = ('id', 'account', 'tag_pool', 'message_direction',
                    'message_cost', 'storage_cost', 'session_cost',
                    'session_unit_cost', 'markup_percent',
                    'message_credit_cost', 'storage_credit_cost',
                    'session_credit_cost', 'session_length_credit_cost',
                    'session_unit_time')

    search_fields = (
        'tag_pool__name', 'tag_pool__description', 'account__account_number',
        'account__user__email', 'account__description')
    list_filter = ('tag_pool', 'message_direction')
    form = MessageCostForm


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'created', 'account_number', 'transaction_type',
                    'tag_pool_name', 'tag_name', 'message_direction',
                    'session_created', 'message_cost', 'storage_cost',
                    'session_cost', 'session_length_cost',
                    'session_unit_cost', 'session_unit_time',
                    'markup_percent', 'provider', 'credit_amount',
                    'message_credits', 'storage_credits',
                    'session_credits', 'session_length_credits',
                    'credit_factor', 'status', 'message_id', 'last_modified')

    readonly_fields = list_display

    search_fields = ('account__account_number', 'tag_pool_name', 'tag_name')
    list_filter = ('message_direction', 'status', 'created', 'last_modified')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, *args, **kwargs):
        return False


class LineItemInline(admin.TabularInline):
    model = LineItem

    readonly_fields = (
        'statement', 'billed_by', 'channel', 'channel_type', 'description',
        'units', 'credits', 'unit_cost', 'cost')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class StatementAdmin(admin.ModelAdmin):
    inlines = [
        LineItemInline,
    ]

    list_display = (
        'account', 'title', 'type', 'from_date', 'to_date', 'created',
        'view_html',
    )

    readonly_fields = (
        'account', 'title', 'type', 'from_date', 'to_date', 'created',
    )

    def view_html(self, obj):
        return format_html('<a href="{0}">html</a>', urlresolvers.reverse(
            'billing:html_statement', kwargs={'statement_id': obj.id}))
    view_html.short_description = "HTML"


admin.site.register(TagPool, TagPoolAdmin)
admin.site.register(Account, AccountAdmin)
admin.site.register(MessageCost, MessageCostAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(Statement, StatementAdmin)
admin.site.register(LowCreditNotification)
admin.site.register(TransactionArchive)
