import pytest
from unittest.mock import patch, MagicMock, mock_open
# Pastikan Anda mengimpor fungsi dari file r2dump
from r2dump import generate_symbols_json

# ==============================================================================
# DATA PALSU UNTUK PENGUJIAN
# ==============================================================================

FAKE_SYMBOLS_OUTPUT = """
   1: 0000000000000000     0 NOTYPE  LOCAL  DEFAULT  ABS
   2: 0000000000012340    56 FUNC    GLOBAL DEFAULT   13 MyNamespace::MyClass::doSomething(int, bool)
   3: 00000000000abcde    24 FUNC    GLOBAL DEFAULT   13 MyNamespace::MyClass::~MyClass()
   4: 0000000000056780   112 FUNC    GLOBAL DEFAULT   13 AnotherClass::anotherMethod(std::string const&)
   5: 0000000000000000     0 NOTYPE  WEAK   DEFAULT  UND std::logic_error::logic_error(char const*)
"""

EXPECTED_RESULT = {
    'library_name': 'libfake.so',
    'classes_found': 2,
    'methods_found': 3,
    'classes': [
        {
            'class_name': 'AnotherClass', 
            'methods': [
                {'name': 'anotherMethod', 'params': '(std::string const&)', 'offset': '0x56780'}
            ]
        },
        {
            'class_name': 'MyNamespace::MyClass', 
            'methods': [
                {'name': '~MyClass', 'params': '()', 'offset': '0xABCDE'},
                {'name': 'doSomething', 'params': '(int, bool)', 'offset': '0x12340'}
            ]
        }
    ]
}

# ==============================================================================
# FUNGSI TES
# ==============================================================================

# Patch os.path.isfile, Popen, dan tempfile secara bersamaan
@patch('r2dump.os.path.isfile', return_value=True)
@patch('r2dump.tempfile.NamedTemporaryFile')
@patch('r2dump.subprocess.Popen')
def test_generate_symbols_json_parsing(mock_popen, mock_tempfile, mock_isfile):
    """
    Tes ini memverifikasi bahwa fungsi generate_symbols_json dapat mem-parsing
    output simbol palsu dengan benar dan menghasilkan struktur data yang diharapkan.
    """
    # 1. SETUP MOCK
    
    # Atur mock untuk Popen
    mock_readelf_process = MagicMock()
    mock_cxxfilt_process = MagicMock()
    mock_popen.side_effect = [mock_readelf_process, mock_cxxfilt_process]

    # Atur mock untuk tempfile.NamedTemporaryFile
    mock_file_handle = mock_open(read_data=FAKE_SYMBOLS_OUTPUT).return_value
    mock_tempfile.return_value.__enter__.return_value = mock_file_handle
    
    # 2. EKSEKUSI
    result = generate_symbols_json('libfake.so')

    # 3. VERIFIKASI
    assert result is not None, "Fungsi seharusnya mengembalikan dictionary, bukan None"
    
    # Normalisasi hasil untuk perbandingan yang andal (mengabaikan urutan)
    def normalize_data(data):
        sorted_classes = sorted(data['classes'], key=lambda x: x['class_name'])
        for cls in sorted_classes:
            cls['methods'] = sorted(cls['methods'], key=lambda x: x['name'])
        data['classes'] = sorted_classes
        return data

    normalized_result = normalize_data(result)
    normalized_expected = normalize_data(EXPECTED_RESULT)

    assert normalized_result == normalized_expected

