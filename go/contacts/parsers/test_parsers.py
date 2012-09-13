from os import path

from django.test import TestCase
from django.conf import settings

from go.contacts.parsers import csv_parser

# sample-contacts.csv
# sample-unicode-contacts.csv
# sample-windows-linebreaks-contacts.csv
# sample-broken-contacts.csv

class CSVParserTestCase(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def fixture(self, fixture_name):
        return open(path.join(settings.PROJECT_ROOT, 'base', 'fixtures',
            fixture_name))

    def test_guess_headers_and_row_without_headers(self):
        csv_file = self.fixture('sample-contacts.csv')
        file_path, first_two_lines = csv_parser.get_file_hints(csv_file)
        data = csv_parser.guess_headers_and_row(first_two_lines)
        has_headers, known_headers, sample_row = data
        self.assertFalse(has_headers)
        self.assertEqual(known_headers, csv_parser.DEFAULT_HEADERS)

    def test_guess_headers_and_row_with_headers(self):
        csv_file = self.fixture('sample-contacts-with-headers.csv')
        file_path, first_two_lines = csv_parser.get_file_hints(csv_file)
        data = csv_parser.guess_headers_and_row(first_two_lines)
        has_headers, known_headers, sample_row = data
        self.assertTrue(has_headers)
        self.assertEqual(known_headers, csv_parser.DEFAULT_HEADERS)
        self.assertEqual(sample_row, {
            'name': 'Name 1',
            'surname': 'Surname 1',
            'msisdn': '+27761234561',
            })

    def test_contacts_parsing(self):
        csv_file = self.fixture('sample-contacts-with-headers.csv')
        contacts = list(csv_parser.parse_contacts_file(csv_file,
                        ['name', 'surname', 'msisdn'], has_header=True))
        self.assertEqual(contacts, [
            (1, {
                'msisdn': '+27761234561',
                'surname': 'Surname 1',
                'name': 'Name 1'}),
            (2, {
                'msisdn': '+27761234562',
                'surname': 'Surname 2',
                'name': 'Name 2'}),
            (3, {
                'msisdn': '+27761234563',
                'surname': 'Surname 3',
                'name': 'Name 3'}),
            ])
