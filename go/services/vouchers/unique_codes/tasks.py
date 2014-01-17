import sys
import traceback

from celery.task import task

from django.conf import settings
from django.core.mail import send_mail
from django.core.files.storage import default_storage
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from go.base.models import UserProfile
from go.vumitools.api import VumiUserApi

from go.services.vouchers.parsers import get_parser
from go.services.vouchers.unique_codes.service import UniqueCodeService


@task(ignore_result=True)
def import_unique_codes_file(account_key, unique_code_pool_key, file_name,
                             file_path, content_type):
    """Parse the file at ``file_path`` and import the unique codes into the
    pool with the given ``unique_code_pool_key``.
    """

    user_api = VumiUserApi.from_config_sync(account_key,
                                            settings.VUMI_API_CONFIG)

    user_profile = UserProfile.objects.get(user_account=account_key)

    store = user_api.unique_code_pool_store
    unique_code_pool = store.get_pool_by_key(unique_code_pool_key)

    voucher_service = UniqueCodeService()

    try:
        parser = get_parser(file_path, content_type)
        for unique_codes in parser.read():
            voucher_service.import_unique_codes(unique_code_pool,
                                                unique_codes)

        send_mail(
            "Unique codes import completed successfully.",
            render_to_string('unique_codes/email/import_completed.txt', {
                'user': user_profile.user,
                'file_name': file_name
            }), settings.DEFAULT_FROM_EMAIL, [user_profile.user.email],
            fail_silently=False)

    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        send_mail(
            "Something went wrong while importing the unique codes.",
            render_to_string('unique_codes/email/import_failed.txt', {
                'user': user_profile.user,
                'account_key': account_key,
                'file_name': file_name,
                'file_path': file_path,
                'exception_type': exc_type,
                'exception_value': mark_safe(exc_value),
                'exception_traceback': mark_safe(
                    traceback.format_tb(exc_traceback)),
            }), settings.DEFAULT_FROM_EMAIL, [
                user_profile.user.email,
                'support@vumi.org',
            ], fail_silently=False)

    finally:
        default_storage.delete(file_path)
