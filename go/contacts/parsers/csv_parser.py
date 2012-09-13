import csv
import uuid
import os.path

from go.vumitools.contact import Contact

from django.utils.datastructures import SortedDict
from django.core.files.base import File
from django.core.files.storage import default_storage

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


DEFAULT_HEADERS = {
    'name': 'Name',
    'surname': 'Surname',
    'bbm_pin': 'BBM Pin',
    'msisdn': 'Contact Number',
    'gtalk_id': 'GTalk (or XMPP) address',
    'dob': 'Date of Birth',
    'facebook_id': 'Facebook ID',
    'twitter_handle': 'Twitter handle',
    'email_address': 'Email address',
}

def read_data_from_csv_file(csvfile, field_names):
    dialect = csv.Sniffer().sniff(csvfile.read(1024))
    csvfile.seek(0)
    reader = csv.DictReader(csvfile, field_names, dialect=dialect)
    for row in reader:
        # Only process rows that actually have data
        if any([column for column in row]):
            # Our Riak client requires unicode for all keys & values stored.
            unicoded_row = dict([(key, unicode(value, 'utf-8'))
                                    for key, value in row.items()])
            yield unicoded_row

def guess_headers_and_row(csv_data):
    """
    Take a sample from the CSV data and determine if it has a header
    and provide a sample of the header if found along with existing
    values matched against the known headers.

    returns a Tuple:

        (header_found, known_headers, sample_data_row)
    """
    sio = StringIO(csv_data)
    dialect = csv.Sniffer().sniff(sio.read(1024))
    sio.seek(0)

    [first_row, second_row] = csv.reader(sio, dialect=dialect)

    default_headers = DEFAULT_HEADERS.copy()

    # Importing here to prevent circular import errors
    from go.contacts.utils import is_header_row
    if is_header_row(first_row):
        sample_row = SortedDict(zip(first_row, second_row))
        for column in first_row:
            default_headers.setdefault(column, column)
        return True, default_headers, sample_row
    return (False, default_headers,
        SortedDict([(column, None) for column in first_row]))


def get_file_hints(content_file):
    """
    Grab the first two lines from the file without parsing the full
    file. It returns the temporary file path where the uploaded file
    is stored the first two lines of the file.
    """
    # Save the file object temporarily so we can present
    # some UI to help the user figure out which columns are
    # what of what type.
    temp_file_name = '%s.csv' % (uuid.uuid4().hex,)
    django_content_file = File(file=content_file, name=temp_file_name)
    temp_file_path = default_storage.save(os.path.join('tmp', temp_file_name),
        django_content_file)
    # Store the first two lines in the session, we'll present these
    # in the UI on the following page to help the user determine
    # which column represents what.
    content_file.seek(0)
    first_two_lines = '\n'.join([
        content_file.readline().strip() for i in range(2)])

    return temp_file_path, first_two_lines

def parse_contacts_file(csv_file, field_names, has_header,
    excluded_attributes=['user_account', 'created_at', 'extra', 'groups']):
    """
    Parses the CSV data and returns dictionaries ready to be fed
    the ContactStore.new_contact method.

    We need to know what we cannot set to avoid a CSV import overwriting
    things like account details. Excluded attributes is a list of contact
    attributes that are to be ignored.

    """
    data_dictionaries = read_data_from_csv_file(csv_file, field_names)

    known_attributes = set([attribute
        for attribute in Contact.field_descriptors.keys()
        if attribute not in excluded_attributes])

    # It's a generator so loop over it and save as contacts
    # in the contact_store, normalizing anything we need to
    for counter, data_dictionary in enumerate(data_dictionaries):

        # If we've determined that the first line of the file is
        # a header then skip it.
        if has_header and counter == 0:
            continue

        # Populate this with whatever we'll be sending to the
        # contact to be saved
        contact_dictionary = {}
        for key, value in data_dictionary.items():
            if key in known_attributes:
                contact_dictionary[key] = value
            else:
                extra = contact_dictionary.setdefault('extra', {})
                extra[key] = value

        yield (counter if has_header else counter + 1, contact_dictionary)
