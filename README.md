# r2dump-toolkit
A toolkit to analyze and diff C++ symbols from .so files.

Cara pakainya sekarang jauh lebih mudah karena sudah menjadi toolkit yang bisa diinstal. Berikut adalah panduan lengkapnya, khusus untuk penggunaan di Termux.

Langkah 1: Instalasi Toolkit
Anda tidak perlu lagi menjalankan python r2dump.py. Sebagai gantinya, instal toolkit ini langsung dari repositori GitHub Anda. Cukup jalankan perintah ini sekali saja di Termux:

pip install git+https://github.com/LuululaleW/r2dump-toolkit.git

Tambahkan flag --force-reinstall dan --no-cache-dir untuk memastikan pip mengunduh versi terbaru dari file Anda dan tidak menggunakan cache yang lama.

pip install --force-reinstall --no-cache-dir git+https://github.com/LuululaleW/r2dump-toolkit.git

Perintah ini akan mengunduh kode dari GitHub dan menginstalnya sebagai perintah baru di Termux Anda yang bernama r2dump.

Langkah 2: Cara Menggunakan Perintah
Setelah terinstal, Anda bisa menjalankan perintah r2dump dari direktori mana pun di Termux.

A. Untuk Menganalisis Satu File (dump)
Ini adalah mode utama untuk mengekstrak simbol dari sebuah file .so.

Contoh:
Misalkan Anda punya file libgame.so di folder Downloads.

# Jalankan perintah dump pada file tersebut

r2dump dump ~/storage/downloads/libgame.so

Untuk mendapatkan output dalam format JSON, tambahkan --format json:

r2dump dump ~/storage/downloads/libgame.so --format json

Hasilnya akan disimpan dalam folder baru bernama libgame@dump.

B. Untuk Membandingkan Dua File (diff)
Gunakan ini untuk melihat perbedaan antara dua versi library.

Contoh:
Misalkan Anda punya libgame_v1.so dan libgame_v2.so di folder Downloads.

# Bandingkan kedua file

r2dump diff ~/storage/downloads/libgame_v1.so ~/storage/downloads/libgame_v2.so

Hasil perbandingannya (simbol yang ditambah dan dihapus) akan langsung ditampilkan di layar.

Langkah 3 (Sangat Direkomendasikan): Aktifkan Tab Completion
Fitur ini akan membuat penggunaan toolkit Anda terasa sangat cepat dan profesional. Anda hanya perlu mengaturnya sekali.

Jalankan perintah ini untuk mendaftarkan completion untuk r2dump:

eval "$(register-python-argcomplete r2dump)"

Agar fitur ini aktif setiap kali Anda membuka Termux, tambahkan perintah di atas ke file konfigurasi shell Anda.

echo 'eval "$(register-python-argcomplete r2dump)"' >> ~/.bashrc

Tutup dan buka kembali aplikasi Termux Anda.

Sekarang, Anda bisa mengetik r2dump d lalu tekan tombol Tab, dan Termux akan otomatis melengkapinya menjadi r2dump dump. Ini juga berfungsi untuk nama file!
