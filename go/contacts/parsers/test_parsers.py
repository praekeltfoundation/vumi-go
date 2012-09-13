from os import path

from django.test import TestCase
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from go.contacts.parsers.csv_parser import CSVFileParser


class ParserTestCase(TestCase):

    def fixture(self, fixture_name):
        fixture_path = path.join(settings.PROJECT_ROOT, 'base', 'fixtures',
            fixture_name)
        content_file = ContentFile(open(fixture_path, 'r').read())
        return default_storage.save('tmp/%s' % (fixture_name,), content_file)

class CSVParserTestCase(ParserTestCase):

    def setUp(self):
        self.parser = CSVFileParser()

    def test_guess_headers_and_row_without_headers(self):
        csv_file = self.fixture('sample-contacts.csv')
        data = self.parser.guess_headers_and_row(csv_file)
        has_headers, known_headers, sample_row = data
        self.assertFalse(has_headers)
        self.assertEqual(known_headers, self.parser.DEFAULT_HEADERS)

    def test_guess_headers_and_row_with_headers(self):
        csv_file = self.fixture('sample-contacts-with-headers.csv')
        data = self.parser.guess_headers_and_row(csv_file)
        has_headers, known_headers, sample_row = data
        self.assertTrue(has_headers)
        self.assertEqual(known_headers, self.parser.DEFAULT_HEADERS)
        self.assertEqual(sample_row, {
            'name': 'Name 1',
            'surname': 'Surname 1',
            'msisdn': '+27761234561',
            })

    def test_contacts_parsing(self):
        csv_file = self.fixture('sample-contacts-with-headers.csv')
        fp = default_storage.open(csv_file, 'rU')
        contacts = list(self.parser.parse_file(fp,
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


class XLSParserTestCase(ParserTestCase):

    def test_guess_headers_and_row_without_headers(self):
        xls_file = self.fixture('sample-contacts.xls')
        file_path, first_two_lines = xls_parser.get_file_hints(xls_file)
        data = xls_parser.guess_headers_and_row(first_two_lines)
        has_headers, known_headers, sample_row = data
        self.assertFalse(has_headers)
        self.assertEqual(known_headers, xls_parser.DEFAULT_HEADERS)

    def test_guess_headers_and_row_with_headers(self):
        xls_file = self.fixture('sample-contacts-with-headers.xlsx')
        file_path, first_two_lines = xls_parser.get_file_hints(xls_file)
        data = xls_parser.guess_headers_and_row(first_two_lines)
        has_headers, known_headers, sample_row = data
        self.assertTrue(has_headers)
        self.assertEqual(known_headers, xls_parser.DEFAULT_HEADERS)
        self.assertEqual(sample_row, {
            'name': 'Name 1',
            'surname': 'Surname 1',
            'msisdn': '+27761234561',
            })

    def test_contacts_parsing(self):
        xls_file = self.fixture('sample-contacts-with-headers.xlsx')
        contacts = list(xls_parser.parse_contacts_file(xls_file,
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
