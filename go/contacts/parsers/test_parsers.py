from os import path

from django.test import TestCase
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from go.contacts.parsers.csv_parser import CSVFileParser
from go.contacts.parsers.xls_parser import XLSFileParser


class ParserTestCase(TestCase):
    def setUp(self):
        self._fixture_paths = []
        self.parser = self.PARSER_CLASS()

    def tearDown(self):
        for fpath in self._fixture_paths:
            default_storage.delete(fpath)

    def fixture(self, fixture_name):
        fixture_path = path.join(settings.PROJECT_ROOT, 'base', 'fixtures',
            fixture_name)
        content_file = ContentFile(open(fixture_path, 'r').read())
        fpath = default_storage.save('tmp/%s' % (fixture_name,), content_file)
        self._fixture_paths.append(fpath)
        return fpath


class CSVParserTestCase(ParserTestCase):
    PARSER_CLASS = CSVFileParser

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

    def test_guess_headers_and_row_one_column_with_plus(self):
        csv_file = self.fixture('sample-contacts-one-column-with-plus.csv')
        data = self.parser.guess_headers_and_row(csv_file)
        has_headers, known_headers, sample_row = data
        self.assertTrue(has_headers)
        self.assertEqual(known_headers, self.parser.DEFAULT_HEADERS)
        self.assertEqual(sample_row, {'msisdn': '+27761234561'})

    def test_contacts_parsing(self):
        csv_file = self.fixture('sample-contacts-with-headers.csv')
        fp = default_storage.open(csv_file, 'rU')
        contacts = list(self.parser.parse_file(fp, zip(
            ['name', 'surname', 'msisdn'],
            ['string', 'string', 'msisdn_za']), has_header=True))
        self.assertEqual(contacts, [
            {
                'msisdn': '+27761234561',
                'surname': 'Surname 1',
                'name': 'Name 1'},
            {
                'msisdn': '+27761234562',
                'surname': 'Surname 2',
                'name': 'Name 2'},
            {
                'msisdn': '+27761234563',
                'surname': 'Surname 3',
                'name': 'Name 3'},
            ])

    def test_contacts_with_none_entries(self):
        csv_file = self.fixture('sample-contacts-with-headers-and-none.csv')
        fp = default_storage.open(csv_file, 'rU')
        contacts = list(self.parser.parse_file(fp, zip(
            ['name', 'surname', 'msisdn'],
            ['string', 'string', 'msisdn_za']), has_header=True))
        self.assertEqual(contacts, [
            {
                'msisdn': '+27761234561',
                'name': 'Name 1'},
            {
                'msisdn': '+27761234562',
                'name': 'Name 2'},
            {
                'msisdn': '+27761234563',
                'surname': 'Surname 3',
                'name': 'Name 3'},
            ])


class XLSParserTestCase(ParserTestCase):
    PARSER_CLASS = XLSFileParser

    def test_guess_headers_and_row_without_headers(self):
        xls_file = self.fixture('sample-contacts.xls')
        data = self.parser.guess_headers_and_row(xls_file)
        has_headers, known_headers, sample_row = data
        self.assertFalse(has_headers)
        self.assertEqual(known_headers, self.parser.DEFAULT_HEADERS)

    def test_guess_headers_and_row_with_headers(self):
        xls_file = self.fixture('sample-contacts-with-headers.xlsx')
        data = self.parser.guess_headers_and_row(xls_file)
        has_headers, known_headers, sample_row = data
        self.assertTrue(has_headers)
        self.assertTrue('mathare-kiamaiko' in known_headers)
        self.assertTrue('baba dogo' in known_headers)
        self.assertTrue('mathare-kiamaiko' in sample_row)
        self.assertTrue('baba dogo' in sample_row)

    def test_contacts_parsing(self):
        xls_file = self.fixture('sample-contacts-with-headers.xlsx')
        contacts = list(self.parser.parse_file(xls_file, zip(
            ['name', 'surname', 'msisdn'],
            ['string', 'integer', 'number']), has_header=True))
        self.assertEqual(contacts[0], {
                'msisdn': '1.0',
                'surname': '2',
                'name': 'xxx'})
