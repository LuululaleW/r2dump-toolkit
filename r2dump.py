import subprocess
import sys
import os
import re
import time
import argparse
import tempfile
import json
import logging
import colorlog
import argcomplete
from collections import defaultdict
from typing import Dict, List, Optional, Set

# ==============================================================================
# 1. SETUP LOGGING
# ==============================================================================

def setup_logging(level: int = logging.INFO) -> None:
    handler = colorlog.StreamHandler()
    formatter = colorlog.ColoredFormatter(
        '%(log_color)s[%(levelname)-8s]%(reset)s %(message)s',
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    handler.setFormatter(formatter)
    
    logger = colorlog.getLogger()
    if not logger.handlers:
        logger.addHandler(handler)
    logger.setLevel(level)

# ==============================================================================
# 2. UTILITIES & DEPENDENCY MANAGEMENT
# ==============================================================================

def check_command(cmd: str) -> bool:
    try:
        subprocess.run(['command', '-v', cmd], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

def install_dependencies() -> None:
    logging.info("Mencoba menginstal 'binutils'...")
    managers = {
        'pkg': 'pkg update -y && pkg install -y binutils',
        'apt': 'sudo apt update -y && sudo apt install -y binutils',
        'dnf': 'sudo dnf install -y binutils'
    }
    
    for manager, command in managers.items():
        if check_command(manager):
            logging.info(f"Manajer paket '{manager}' terdeteksi. Menjalankan perintah instalasi.")
            try:
                subprocess.run(command.split(), check=True)
                return
            except subprocess.CalledProcessError as e:
                logging.error(f"Instalasi dengan {manager} gagal: {e}")
                continue
    logging.critical("Tidak dapat menemukan manajer paket yang didukung. Harap instal 'binutils' secara manual.")
    sys.exit(1)

# ==============================================================================
# 3. CORE SYMBOL EXTRACTION LOGIC
# ==============================================================================

def generate_symbols_json(lib_path: str) -> Optional[Dict]:
    if not os.path.isfile(lib_path):
        logging.error(f"File tidak ditemukan: {lib_path}")
        return None

    logging.info(f"Mengekstrak simbol dari: {os.path.basename(lib_path)}")
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=True, encoding='utf-8') as temp_file:
            p1 = subprocess.Popen(['readelf', '-Ws', lib_path], stdout=subprocess.PIPE)
            p2 = subprocess.Popen(['c++filt'], stdin=p1.stdout, stdout=temp_file)
            p1.stdout.close()
            p2.wait()
            temp_file.seek(0)
            lines = temp_file.readlines()
    except Exception as e:
        logging.error(f"Gagal saat mengekstrak simbol: {e}")
        return None

    classes: Dict[str, List[Dict]] = defaultdict(list)
    method_count = 0
    
    # REGEX FINAL YANG DIPERBAIKI
    pattern = re.compile(
        r"^\s*\d+:\s+"             # Symbol index
        r"([0-9a-fA-F]{8,16})\s+"   # Grup 1: Offset
        r"\d+\s+(?:FUNC|OBJECT)"   # Symbol size and type
        r"\s+\w+\s+\w+\s+\d+\s+"    # Binding, Visibility, Ndx
        r"(.+?::)"                 # Grup 2: Nama kelas/namespace (non-greedy)
        r"([^(:)]+)"               # Grup 3: Nama metode
        r"(\(.*\))"                # Grup 4: Parameter
    )

    for line in lines:
        match = pattern.search(line)
        if not match or match.group(1).lstrip('0') == "":
            continue
        
        offset, class_path, method_name, params = match.groups()
        
        class_path = class_path.rstrip(':')
        
        classes[class_path].append({
            "name": method_name.strip(), 
            "params": params.strip(), 
            "offset": f"0x{int(offset, 16):X}"
        })
        method_count += 1

    logging.debug(f"Ditemukan {len(classes)} kelas dan {method_count} metode.")
    return {
        "library_name": os.path.basename(lib_path),
        "classes_found": len(classes),
        "methods_found": method_count,
        "classes": [{"class_name": k, "methods": sorted(v, key=lambda x: x['name'])} for k, v in sorted(classes.items())]
    }

# ==============================================================================
# 4. COMMAND HANDLERS (DUMP & DIFF)
# ==============================================================================

def perform_dump(args: argparse.Namespace) -> None:
    start_time = time.time()
    data = generate_symbols_json(args.file)
    if not data:
        sys.exit(1)

    clean_lib_name = data['library_name'].replace('.so', '').replace('lib', '', 1)
    output_path = f"{clean_lib_name}@dump"
    os.makedirs(output_path, exist_ok=True)
    
    if args.format == 'json':
        output_file = os.path.join(output_path, f"{clean_lib_name}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    else:
        output_file = os.path.join(output_path, f"{clean_lib_name}.dump.h")
        with open(output_file, "w", encoding="utf-8") as out:
            for cls in data['classes']:
                out.write(f"class {cls['class_name']} {{\npublic:\n")
                for method in cls['methods']:
                    out.write(f"    {method['name']}{method['params']}; // {method['offset']}\n")
                out.write("};\n\n")

    logging.info(f"Output disimpan di: {output_file}")
    logging.info(f"Total Kelas: {data['classes_found']}, Total Metode: {data['methods_found']}")
    logging.info(f"Selesai dalam {time.time() - start_time:.2f} detik.")

def perform_diff(args: argparse.Namespace) -> None:
    logging.info(f"Memulai perbandingan antara {os.path.basename(args.file1)} dan {os.path.basename(args.file2)}")
    start_time = time.time()
    
    data1 = generate_symbols_json(args.file1)
    data2 = generate_symbols_json(args.file2)

    if not data1 or not data2:
        logging.critical("Perbandingan dibatalkan karena salah satu file gagal diproses.")
        sys.exit(1)

    def get_symbol_set(data: Dict) -> Set[str]:
        return {f"{cls['class_name']}::{m['name']}{m['params']}" for cls in data.get('classes', []) for m in cls.get('methods', [])}

    symbols1 = get_symbol_set(data1)
    symbols2 = get_symbol_set(data2)
    added = sorted(list(symbols2 - symbols1))
    removed = sorted(list(symbols1 - symbols2))
    
    print("\n\033[33;1m" + "="*50 + "\033[0m")
    print("\033[33;1mHASIL PERBANDINGAN SIMBOL\033[0m")
    print("\033[33;1m" + "="*50 + "\033[0m")
    
    print(f"\n\033[32;1m[+] SIMBOL DITAMBAHKAN ({len(added)}) di {data2['library_name']}:\033[0m")
    if added: [print(f"  {s}") for s in added]
    else: print("  Tidak ada.")

    print(f"\n\033[31;1m[-] SIMBOL DIHAPUS ({len(removed)}) dari {data1['library_name']}:\033[0m")
    if removed: [print(f"  {s}") for s in removed]
    else: print("  Tidak ada.")
    
    print("\033[33;1m" + "="*50 + "\033[0m")
    logging.info(f"Perbandingan selesai dalam {time.time() - start_time:.2f} detik.")

# ==============================================================================
# 5. MAIN EXECUTION & ARGUMENT PARSING
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Toolkit analisis simbol C++ untuk file .so.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG) logging.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress INFO messages.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Perintah yang tersedia")

    parser_dump = subparsers.add_parser("dump", help="Mengekstrak simbol dari satu file .so")
    parser_dump.add_argument("file", help="Path ke file .so").completer = argcomplete.FilesCompleter()
    parser_dump.add_argument("--format", choices=['text', 'json'], default='text', help="Format output")
    parser_dump.set_defaults(func=perform_dump)
    
    parser_diff = subparsers.add_parser("diff", help="Membandingkan dua file .so")
    parser_diff.add_argument("file1", help="Path ke file .so versi lama").completer = argcomplete.FilesCompleter()
    parser_diff.add_argument("file2", help="Path ke file .so versi baru").completer = argcomplete.FilesCompleter()
    parser_diff.set_defaults(func=perform_diff)

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    log_level = logging.INFO
    if args.verbose: log_level = logging.DEBUG
    if args.quiet: log_level = logging.WARNING
    setup_logging(log_level)

    if not all(check_command(cmd) for cmd in ['readelf', 'c++filt']):
        logging.warning("Dependensi 'readelf' atau 'c++filt' tidak ditemukan.")
        install_dependencies()
        if not all(check_command(cmd) for cmd in ['readelf', 'c++filt']):
            logging.critical("Gagal menginstal dependensi. Keluar.")
            sys.exit(1)

    args.func(args)

if __name__ == "__main__":
    main()
