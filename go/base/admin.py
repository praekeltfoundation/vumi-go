from django.contrib import admin

from go.base.models import UserProfile, UserOrganisation


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'organisation', 'is_admin')

admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(UserOrganisation)
