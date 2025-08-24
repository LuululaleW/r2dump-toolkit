# r2dump.py

import subprocess
import json
import re
from collections import defaultdict

def generate_symbols_json(library_path):
    """
    Menganalisis file library ELF, mengekstrak simbol, melakukan demangle,
    dan menghasilkan struktur data JSON yang berisi kelas dan metode.
    """
    symbols = []

    # Langkah 1: Jalankan readelf untuk mendapatkan simbol dari library
    try:
        readelf_process = subprocess.Popen(
            ['readelf', '-s', '--wide', library_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = readelf_process.communicate()
        if readelf_process.returncode != 0:
            print(f"Error executing readelf: {stderr}")
            return None
        
        mangled_symbols = re.findall(r'\s+([0-9a-fA-F]+)\s+\d+\s+FUNC\s+GLOBAL\s+DEFAULT\s+\d+\s+(_Z\S+)', stdout)
        
        if not mangled_symbols:
            print("No mangled symbols found.")
            return None

    except FileNotFoundError:
        print("Error: 'readelf' command not found. Please ensure binutils is installed.")
        return None

    # Langkah 2: Jalankan c++filt untuk demangle semua simbol yang ditemukan
    try:
        mangled_input = "\n".join([symbol for offset, symbol in mangled_symbols])
        cxxfilt_process = subprocess.Popen(
            ['c++filt'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        demangled_output, stderr = cxxfilt_process.communicate(input=mangled_input)
        if cxxfilt_process.returncode != 0:
            print(f"Error executing c++filt: {stderr}")
            return None
        
        demangled_names = demangled_output.strip().split('\n')

    except FileNotFoundError:
        print("Error: 'c++filt' command not found. Please ensure binutils is installed.")
        return None

    if len(mangled_symbols) != len(demangled_names):
        print("Mismatch between mangled and demangled symbols count.")
        return None

    for i, (offset, _) in enumerate(mangled_symbols):
        symbols.append({'offset': f'0x{offset}', 'demangled_name': demangled_names[i]})

    # Langkah 3: Proses simbol yang sudah di-demangle untuk mengelompokkannya ke dalam kelas
    class_map = defaultdict(list)
    total_methods = 0

    for symbol in symbols:
        demangled_name = symbol['demangled_name']
        
        if ' ' in demangled_name:
            demangled_name = demangled_name.split()[-1]

        # Regex yang sudah diperbaiki untuk parsing nama metode dan kelas
        match = re.match(r'^(.*)::(~?\w+)(\(.*\))$', demangled_name)

        if match:
            class_name = match.group(1)
            method_name = match.group(2)
            params = match.group(3)
            
            class_map[class_name].append({
                'name': method_name,
                'offset': symbol['offset'],
                'params': params
            })
            total_methods += 1

    # Langkah 4: Format output sesuai struktur JSON yang diharapkan
    output_data = {
        'library_name': library_path,
        'classes_found': len(class_map),
        'methods_found': total_methods,
        'classes': []
    }

    for class_name, methods in class_map.items():
        output_data['classes'].append({
            'class_name': class_name,
            'methods': methods
        })

    return output_data

if __name__ == '__main__':
    # Anda bisa menambahkan fungsi main di sini jika diperlukan
    pass
