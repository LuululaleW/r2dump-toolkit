# r2dump.py

import subprocess
import json
import re
import argparse
import sys
import os
from collections import defaultdict

def search_strings_in_file(library_path, keyword):
    """
    Mencari string keyword di seluruh file binary dan menampilkan alamatnya.
    """
    if not os.path.exists(library_path):
        print(f"Error: File tidak ditemukan di '{library_path}'")
        return

    print(f"Mencari string '{keyword}' di dalam {os.path.basename(library_path)}...")
    try:
        # Menggunakan 'strings' dan 'grep' untuk efisiensi
        strings_proc = subprocess.Popen(['strings', '-a', '-t', 'x', library_path], stdout=subprocess.PIPE, text=True, errors='ignore')
        grep_proc = subprocess.Popen(['grep', '-i', keyword], stdin=strings_proc.stdout, stdout=subprocess.PIPE, text=True, errors='ignore')
        
        # Tutup stdout dari strings_proc agar grep bisa selesai
        strings_proc.stdout.close()
        
        output, _ = grep_proc.communicate()

        if output:
            print("="*20 + " HASIL PENCARIAN " + "="*20)
            print(output)
            print("="*58)
        else:
            print(f"String '{keyword}' tidak ditemukan di dalam file.")

    except FileNotFoundError:
        print("Error: Perintah 'strings' atau 'grep' tidak ditemukan. Pastikan keduanya terinstal.")
    except Exception as e:
        print(f"Terjadi error saat mencari: {e}")


def generate_symbols_json(library_path):
    # ... (fungsi ini tetap sama seperti sebelumnya)
    if not os.path.exists(library_path):
        print(f"Error: File tidak ditemukan di '{library_path}'")
        return None
    symbols = []
    try:
        nm_process = subprocess.Popen(['nm', '-D', library_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='ignore')
        stdout, stderr = nm_process.communicate()
        if nm_process.returncode != 0:
            nm_process = subprocess.Popen(['nm', library_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='ignore')
            stdout, stderr = nm_process.communicate()
            if nm_process.returncode != 0:
                print(f"Error executing nm: {stderr}")
                return None
        mangled_symbols = re.findall(r'^([0-9a-fA-F]+)\s+[TtWw]\s+(_Z\S+)', stdout, re.MULTILINE)
        if not mangled_symbols:
            print("No mangled C++ symbols found using 'nm'. Mungkin simbol telah di-strip.")
            return None
    except FileNotFoundError:
        print("Error: 'nm' command not found. Pastikan binutils terinstal (`pkg install binutils`)")
        return None
    try:
        mangled_input = "\n".join([symbol for offset, symbol in mangled_symbols])
        cxxfilt_process = subprocess.Popen(['c++filt'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        demangled_output, stderr = cxxfilt_process.communicate(input=mangled_input)
        if cxxfilt_process.returncode != 0:
            print(f"Error executing c++filt: {stderr}")
            return None
        demangled_names = demangled_output.strip().split('\n')
    except FileNotFoundError:
        print("Error: 'c++filt' command not found. Pastikan binutils terinstal.")
        return None
    if len(mangled_symbols) != len(demangled_names):
        return None
    for i, (offset, _) in enumerate(mangled_symbols):
        symbols.append({'offset': f'0x{offset.zfill(8)}', 'demangled_name': demangled_names[i]})
    class_map = defaultdict(list)
    total_methods = 0
    unique_methods = set()
    for symbol in symbols:
        demangled_name = symbol['demangled_name']
        if ' ' in demangled_name:
            demangled_name = demangled_name.split()[-1]
        match = re.match(r'^(.*)::(~?\w+)(\(.*\))$', demangled_name)
        if match:
            method_signature = f"{demangled_name}@{symbol['offset']}"
            if method_signature in unique_methods:
                continue
            unique_methods.add(method_signature)
            class_name = match.group(1)
            method_name = match.group(2)
            params = match.group(3)
            class_map[class_name].append({'name': method_name, 'offset': symbol['offset'], 'params': params})
            total_methods += 1
    output_data = {'library_name': os.path.basename(library_path), 'classes_found': len(class_map), 'methods_found': total_methods, 'classes': []}
    for class_name, methods in sorted(class_map.items()):
        output_data['classes'].append({'class_name': class_name, 'methods': sorted(methods, key=lambda x: x['name'])})
    return output_data

def main():
    parser = argparse.ArgumentParser(description="Analisis simbol C++ dari file .so.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-command help")

    parser_dump = subparsers.add_parser("dump", help="Menganalisis simbol dari satu file .so.")
    parser_dump.add_argument("file", help="Path ke file .so.")
    parser_dump.add_argument("--format", choices=['txt', 'json'], default='txt', help="Format output.")
    parser_dump.add_argument("--filter", type=str, help="Filter hasil berdasarkan kata kunci.")

    parser_diff = subparsers.add_parser("diff", help="Membandingkan simbol dari dua file .so.")
    parser_diff.add_argument("file1", help="Path ke file .so pertama.")
    parser_diff.add_argument("file2", help="Path ke file .so kedua.")
    
    # --- PERINTAH BARU: SEARCH ---
    parser_search = subparsers.add_parser("search", help="Mencari string di seluruh file binary.")
    parser_search.add_argument("file", help="Path ke file .so.")
    parser_search.add_argument("keyword", help="String yang ingin dicari (case-insensitive).")

    args = parser.parse_args()

    if args.command == "dump":
        print(f"Menganalisis simbol di {args.file} menggunakan 'nm'...")
        result = generate_symbols_json(args.file)
        if result:
            if args.filter:
                keyword = args.filter.lower()
                filtered_classes = []
                for cls in result['classes']:
                    if keyword in cls['class_name'].lower():
                        filtered_classes.append(cls)
                    else:
                        matching_methods = [m for m in cls['methods'] if keyword in m['name'].lower()]
                        if matching_methods:
                            filtered_classes.append({'class_name': cls['class_name'], 'methods': matching_methods})
                result['classes'] = filtered_classes
            
            lib_name = os.path.basename(args.file)
            output_dir = f"{lib_name}@dump"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "dump.txt")
            with open(output_path, 'w') as f:
                if not result['classes']:
                    f.write(f"Tidak ada simbol yang cocok dengan filter '{args.filter}' ditemukan.\n")
                    print(f"Tidak ada simbol yang cocok dengan filter '{args.filter}' ditemukan.")
                else:
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
        # ... (fungsi diff tidak berubah)
        pass # Isi dengan logika diff yang sudah ada

    elif args.command == "search":
        search_strings_in_file(args.file, args.keyword)

if __name__ == '__main__':
    main()