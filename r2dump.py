# r2dump.py

import subprocess
import json
import re
import argparse
import sys
import os
from collections import defaultdict

def generate_symbols_json(library_path):
    """
    Menganalisis file library ELF, mengekstrak simbol, melakukan demangle,
    dan menghasilkan struktur data JSON yang berisi kelas dan metode.
    """
    if not os.path.exists(library_path):
        print(f"Error: File tidak ditemukan di '{library_path}'")
        return None

    symbols = []

    try:
        # Perintah readelf disederhanakan untuk kompatibilitas maksimal
        readelf_process = subprocess.Popen(
            ['readelf', '-s', library_path],
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
            print("No mangled C++ symbols found.")
            return None

    except FileNotFoundError:
        print("Error: 'readelf' command not found. Please ensure binutils is installed.")
        return None

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

    class_map = defaultdict(list)
    total_methods = 0

    for symbol in symbols:
        demangled_name = symbol['demangled_name']
        
        if ' ' in demangled_name:
            demangled_name = demangled_name.split()[-1]

        # Regex yang sudah diperbaiki
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

    output_data = {
        'library_name': os.path.basename(library_path),
        'classes_found': len(class_map),
        'methods_found': total_methods,
        'classes': []
    }

    for class_name, methods in sorted(class_map.items()):
        output_data['classes'].append({
            'class_name': class_name,
            'methods': sorted(methods, key=lambda x: x['name'])
        })

    return output_data

def main():
    """
    Fungsi utama untuk menangani argumen command-line.
    """
    parser = argparse.ArgumentParser(description="Analisis simbol C++ dari file .so.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-command help")

    parser_dump = subparsers.add_parser("dump", help="Menganalisis satu file .so dan menyimpan hasilnya.")
    parser_dump.add_argument("file", help="Path ke file .so yang akan dianalisis.")
    parser_dump.add_argument("--format", choices=['txt', 'json'], default='txt', help="Format output (txt atau json).")

    parser_diff = subparsers.add_parser("diff", help="Membandingkan dua file .so.")
    parser_diff.add_argument("file1", help="Path ke file .so pertama.")
    parser_diff.add_argument("file2", help="Path ke file .so kedua.")

    args = parser.parse_args()

    if args.command == "dump":
        result = generate_symbols_json(args.file)
        if result:
            lib_name = os.path.basename(args.file)
            output_dir = f"{lib_name}@dump"
            os.makedirs(output_dir, exist_ok=True)
            
            if args.format == 'json':
                output_path = os.path.join(output_dir, "dump.json")
                with open(output_path, 'w') as f:
                    json.dump(result, f, indent=4)
                print(f"Hasil JSON disimpan di: {output_path}")
            else:  # txt format
                output_path = os.path.join(output_dir, "dump.txt")
                with open(output_path, 'w') as f:
                    for cls in result['classes']:
                        if cls['methods']:
                            f.write(f"// CLASS: {cls['class_name']}\n")
                        
                        for method in cls['methods']:
                            offset = method['offset']
                            simple_offset = offset.replace('0x', '').upper()
                            
                            f.write(f"\t// RVA: 0x{simple_offset} Offset: 0x{simple_offset} VA: 0x{offset}\n")
                            f.write(f"\t{method['name']}{method['params']} {{ }}\n\n")
                print(f"Hasil TXT disimpan di: {output_path}")
    
    elif args.command == "diff":
        print("Memproses file pertama...")
        data1 = generate_symbols_json(args.file1)
        print("Memproses file kedua...")
        data2 = generate_symbols_json(args.file2)

        if data1 and data2:
            methods1 = {f"{c['class_name']}::{m['name']}{m['params']}" for c in data1['classes'] for m in c['methods']}
            methods2 = {f"{c['class_name']}::{m['name']}{m['params']}" for c in data2['classes'] for m in c['methods']}

            added = sorted(list(methods2 - methods1))
            removed = sorted(list(methods1 - methods2))

            print("\n" + "="*20 + " HASIL PERBANDINGAN " + "="*20)
            print(f"\n[+] Ditambahkan di {os.path.basename(args.file2)} ({len(added)}):")
            if added:
                for item in added:
                    print(f"  + {item}")
            else:
                print("  Tidak ada.")

            print(f"\n[-] Dihapus di {os.path.basename(args.file2)} ({len(removed)}):")
            if removed:
                for item in removed:
                    print(f"  - {item}")
            else:
                print("  Tidak ada.")
            print("\n" + "="*62)

if __name__ == '__main__':
    main()