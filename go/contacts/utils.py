import os

from vumi.utils import import_module

def get_file_extension(file_name):
    name, extension = os.path.splitext(file_name)
    separator, suffix = extension.rsplit('.', 1)
    return suffix

def get_parser(file_name):
    extension = get_file_extension(file_name)

    parser = {
        'csv': 'go.contacts.parsers.csv_parser',
        'xls': 'go.contacts.parser.xls_parser',
        'xlsx': 'go.contacts.parser.xls_parser',
    }.get(extension)

    if parser:
        return (extension, import_module(parser))

def is_header_row(columns):
    """
    Determines whether the given columns have something that might hint
    at the row being a row with column headers and not column values.
    """
    column_set = set([column.lower() for column in columns])
    hint_set = set(['phone', 'contact', 'msisdn', 'number'])
    return hint_set.intersection(column_set)


def store_file_hints_in_session(request, path, data):
    """
    Stores the hints in the request session. Allows us to continue with
    handling the file after the first two lines of data and header columns
    have been verified by the user.
    """
    # Not too happy with this method but I don't want to
    # be writing the same session keys everywhere.
    request.session['uploaded_contacts_path'] = path
    request.session['uploaded_contacts_data'] = data
    return request


def get_file_hints_from_session(request):
    return [
        request.session['uploaded_contacts_path'],
        request.session['uploaded_contacts_data'],
    ]


def clear_file_hints_from_session(request):
    del request.session['uploaded_contacts_data']
    del request.session['uploaded_contacts_path']


def has_uncompleted_contact_import(request):
    return (('uploaded_contacts_data' in request.session)
        and ('uploaded_contacts_path' in request.session))

