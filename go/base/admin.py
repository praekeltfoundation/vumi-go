from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _

from go.base.models import GoUser, UserProfile, UserOrganisation
from go.base.forms import GoUserCreationForm, GoUserChangeForm


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    fields = ('organisation', 'is_admin', 'user_account')
    readonly_fields = ('user_account',)
    can_delete = False


class GoUserAdmin(UserAdmin):
    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []
        return super(GoUserAdmin, self).get_inline_instances(request, obj=obj)

    # loginas form template
    change_form_template = 'loginas/change_form.html'

    # The forms to add and change user instances
    inlines = (UserProfileInline,)

    # The fields to be used in displaying the User model.
    # These override the definitions on the base UserAdmin
    # that reference the removed 'username' field
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    form = GoUserChangeForm
    add_form = GoUserCreationForm
    list_display = ('email', 'first_name', 'last_name', 'is_superuser',
                    'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'organisation', 'is_admin')
    search_fields = ('user__email', 'user__first_name', 'user__last_name',
                     'organisation')


admin.site.register(GoUser, GoUserAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(UserOrganisation)
