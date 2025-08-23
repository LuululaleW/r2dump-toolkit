import pytest
from unittest.mock import patch, MagicMock, mock_open
from r2dump import generate_symbols_json

# ==============================================================================
# DATA PALSU UNTUK PENGUJIAN
# ==============================================================================

# Ini adalah contoh output yang akan kita pura-pura didapatkan dari `readelf | c++filt`
FAKE_SYMBOLS_OUTPUT = """
   1: 0000000000000000     0 NOTYPE  LOCAL  DEFAULT  ABS
   2: 0000000000012340    56 FUNC    GLOBAL DEFAULT   13 MyNamespace::MyClass::doSomething(int, bool)
   3: 00000000000abcde    24 FUNC    GLOBAL DEFAULT   13 MyNamespace::MyClass::~MyClass()
   4: 0000000000056780   112 FUNC    GLOBAL DEFAULT   13 AnotherClass::anotherMethod(std::string const&)
   5: 0000000000000000     0 NOTYPE  WEAK   DEFAULT  UND std::logic_error::logic_error(char const*)
"""

# Ini adalah hasil JSON yang kita harapkan dari parsing data di atas
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

# Menggunakan @patch untuk "mencegat" panggilan ke subprocess.Popen
@patch('r2dump.subprocess.Popen')
def test_generate_symbols_json_parsing(mock_popen):
    """
    Tes ini memverifikasi bahwa fungsi generate_symbols_json dapat mem-parsing
    output simbol palsu dengan benar dan menghasilkan struktur data yang diharapkan.
    """
    # 1. SETUP MOCK: Atur agar Popen mengembalikan data palsu kita
    # Kita membuat mock untuk proses `readelf` dan `c++filt`
    mock_process = MagicMock()
    mock_process.stdout.read.return_value = FAKE_SYMBOLS_OUTPUT.encode('utf-8')
    mock_process.communicate.return_value = (FAKE_SYMBOLS_OUTPUT.encode('utf-8'), b'')
    mock_popen.return_value = mock_process
    
    # Menambahkan mock untuk 'tempfile.NamedTemporaryFile'
    # agar kita tidak benar-benar membuat file di sistem
    with patch('r2dump.tempfile.NamedTemporaryFile', mock_open(read_data=FAKE_SYMBOLS_OUTPUT)) as mock_file:
    
        # 2. EKSEKUSI: Panggil fungsi yang ingin kita uji
        result = generate_symbols_json('libfake.so')

        # 3. VERIFIKASI (ASSERT): Periksa apakah hasilnya sesuai harapan
        assert result is not None, "Fungsi seharusnya mengembalikan dictionary, bukan None"
        assert result['classes_found'] == EXPECTED_RESULT['classes_found']
        assert result['methods_found'] == EXPECTED_RESULT['methods_found']
        assert result['classes'] == EXPECTED_RESULT['classes']

