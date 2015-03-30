from go.contacts import tasks, utils
from go.contacts.parsers import ContactFileParser


class ContactImportException(Exception):
    """
    Exception raised when an import handler determines that an import cannot
    succeed.
    """


def dispatch_import_task(import_task, request, group, check_fields=None):
    file_name, file_path = utils.get_file_hints_from_session(request)
    file_type, parser = ContactFileParser.get_parser(file_name)
    has_header, _, sample_row = parser.guess_headers_and_row(file_path)

    # Grab the selected field names from the submitted form
    # by looping over the expect n number of `column-n` keys being
    # posted
    field_names = [request.POST.get('column-%s' % i) for i in
                   range(len(sample_row))]
    normalizers = [request.POST.get('normalize-%s' % i, '')
                   for i in range(len(sample_row))]
    fields = zip(field_names, normalizers)

    if check_fields is not None:
        check_fields(dict(fields))

    import_task.delay(
        request.user_api.user_account_key, group.key, file_name,
        file_path, fields, has_header)

    utils.clear_file_hints_from_session(request)


def check_import_new_contacts_fields(fields):
    if u'msisdn' not in fields:
        raise ContactImportException("Please specify a Contact Number field.")


def handle_import_new_contacts(request, group):
    return dispatch_import_task(
        tasks.import_new_contacts_file, request, group,
        check_import_new_contacts_fields)


def handle_import_upload_is_truth(request, group):
    return dispatch_import_task(
        tasks.import_upload_is_truth_contacts_file, request, group)


def handle_import_existing_is_truth(request, group):
    return dispatch_import_task(
        tasks.import_existing_is_truth_contacts_file, request, group)
