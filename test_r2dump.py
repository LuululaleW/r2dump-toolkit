# test_r2dump.py

import unittest
from unittest.mock import patch, MagicMock
from r2dump import generate_symbols_json

# Mock output dari readelf
MOCK_READELF_OUTPUT = """
Symbol table '.dynsym' contains 3 entries:
   Num:    Value          Size Type    Bind   Vis      Ndx Name
     1: 0000000000012340    45 FUNC    GLOBAL DEFAULT   13 _ZN11MyNamespace8MyClass11doSomethingEib
     2: 00000000000abcde    30 FUNC    GLOBAL DEFAULT   13 _ZN11MyNamespace8MyClassD1Ev
     3: 0000000000056780    60 FUNC    GLOBAL DEFAULT   13 _ZN12AnotherClass13anotherMethodERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEE
"""

# Mock output dari c++filt
MOCK_CXXFILT_OUTPUT = "MyNamespace::MyClass::doSomething(int, bool)\nMyNamespace::MyClass::~MyClass()\nAnotherClass::anotherMethod(std::string const&)\n"


class TestR2Dump(unittest.TestCase):

    @patch('r2dump.subprocess.Popen')
    def test_generate_symbols_json_parsing(self, mock_popen):
        """
        Tes ini memverifikasi bahwa fungsi generate_symbols_json dapat mem-parsing
        output simbol palsu dengan benar dan menghasilkan struktur data yang diharapkan.
        """
        # 1. SETUP MOCK
        mock_readelf_process = MagicMock()
        mock_readelf_process.communicate.return_value = (MOCK_READELF_OUTPUT, '')
        mock_readelf_process.returncode = 0

        mock_cxxfilt_process = MagicMock()
        mock_cxxfilt_process.communicate.return_value = (MOCK_CXXFILT_OUTPUT, '')
        mock_cxxfilt_process.returncode = 0
        
        mock_popen.side_effect = [mock_readelf_process, mock_cxxfilt_process]

        # 2. EKSEKUSI
        result = generate_symbols_json('libfake.so')

        # 3. VERIFIKASI
        self.assertIsNotNone(result, "Fungsi seharusnya mengembalikan dictionary, bukan None")

        def normalize_data(data):
            sorted_classes = sorted(data['classes'], key=lambda x: x['class_name'])
            for cls in sorted_classes:
                cls['methods'] = sorted(cls['methods'], key=lambda x: x['name'])
            data['classes'] = sorted_classes
            return data

        normalized_result = normalize_data(result)
        
        expected_result_adjusted = {
            'library_name': 'libfake.so',
            'classes_found': 2,
            'methods_found': 3,
            'classes': [
                {
                    'class_name': 'AnotherClass',
                    'methods': [{'name': 'anotherMethod', 'offset': '0x56780', 'params': '(std::string const&)'}]
                },
                {
                    'class_name': 'MyNamespace::MyClass',
                    'methods': [
                        {'name': 'doSomething', 'offset': '0x12340', 'params': '(int, bool)'},
                        {'name': '~MyClass', 'offset': '0xabcde', 'params': '()'}
                    ]
                }
            ]
        }
        
        normalized_expected = normalize_data(expected_result_adjusted)

        self.assertEqual(normalized_result, normalized_expected)

if __name__ == '__main__':
    unittest.main()
