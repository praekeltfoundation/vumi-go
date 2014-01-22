import os

from django.conf import settings

from go.base.tests.helpers import GoDjangoTestCase

from go.services.vouchers.parsers import CsvParser, ExcelParser


class TestParsers(GoDjangoTestCase):

    def test_csv_parser(self):
        file_path = os.path.join(settings.PROJECT_ROOT, 'base', 'fixtures',
                                 'sample-airtime-vouchers.csv')

        csv_parser = CsvParser(file_path)
        content = csv_parser.read().next()
        expected_content = ('operator,denomination,voucher\r\n'
                            'Tank,red,Tr0\r\nTank,red,Tr1\r\nTank,blue,Tb0\r\n'
                            'Tank,blue,Tb1\r\nLink,red,Lr0\r\nLink,red,Lr1\r\n'
                            'Link,blue,Lb0\r\nLink,blue,Lb1\r\n')

        self.assertEqual(content, expected_content)

    def test_xls_parser(self):
        file_path = os.path.join(settings.PROJECT_ROOT, 'base', 'fixtures',
                                 'sample-airtime-vouchers.xls')

        excel_parser = ExcelParser(file_path)
        content = excel_parser.read().next()
        expected_content = ('operator,denomination,voucher\r\n'
                            'Tank,red,Tr0\r\nTank,red,Tr1\r\nTank,blue,Tb0\r\n'
                            'Tank,blue,Tb1\r\nLink,red,Lr0\r\nLink,red,Lr1\r\n'
                            'Link,blue,Lb0\r\nLink,blue,Lb1\r\n')

        self.assertEqual(content, expected_content)
