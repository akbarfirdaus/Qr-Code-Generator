# QR Code File Generator

Aplikasi Python sederhana untuk membuat QR Code yang membuka PDF atau gambar dari laptop melalui Wi-Fi/LAN. Ini adalah MVP dengan local file server, tanpa database, login, framework web, atau cloud storage.

QR Code **menyimpan URL**, bukan seluruh isi PDF/gambar. Selama server menyala, HP pada jaringan yang sama dapat membuka file tersebut melalui browser, tanpa koneksi internet.

## Fitur

- Membaca file PDF, JPG, JPEG, dan PNG langsung dari `data/` (ekstensi tidak peka huruf besar/kecil).
- Mengabaikan format lain, subfolder, dan symlink.
- Mendeteksi IPv4 LAN otomatis; tersedia `--host-ip` dan `--port`.
- Mengubah spasi, tanda kurung, Unicode, dan karakter khusus nama file menjadi URL encoding.
- Menyimpan PNG hitam-putih di `output/`, dengan margin empat modul, 16 piksel per modul, koreksi kesalahan M, dan metadata 300 DPI.
- Server HTTP standar Python, dengan respons MIME yang sesuai dan tampilan inline untuk gambar/PDF.
- Menolak traversal, symlink, file di luar `data/`, dan directory listing.
- Tidak mengubah atau menghapus file asli.

## Persyaratan

- Windows dengan Python **3.13** dan VS Code.
- Virtual environment `.venv/` di workspace ini.
- `qrcode` dan `Pillow`; versi yang dipakai tercantum di `requirements.txt`.
- Laptop dan HP terhubung ke Wi-Fi/LAN yang sama dan dapat berkomunikasi antarperangkat.
- Izin menulis ke `output/` dan izin koneksi masuk pada jaringan privat.

Internet hanya diperlukan jika dependency perlu diunduh, bukan saat memakai aplikasi di LAN.

## Struktur folder

```text
Qr qode/
├── .venv/
├── data/                 # PDF/gambar asli; tidak diubah aplikasi
├── output/               # PNG QR; dibuat otomatis
├── main.py
├── test_main.py          # Pengujian otomatis tanpa dependency tambahan
├── requirements.txt
├── README.md
├── PRD.md
└── .gitignore
```

Lokasi `data/` dan `output/` selalu relatif terhadap `main.py`, sehingga tidak bergantung pada folder aktif terminal. File pribadi di `data/` serta hasil `output/` diabaikan oleh Git.

## Instalasi di VS Code pada Windows

Jika baru mengunduh atau clone dari GitHub, `.venv/` dan file pribadi di `data/` tidak disertakan. Buat environment terlebih dahulu jika belum ada:

```powershell
py -3.13 -m venv .venv
```

Kemudian tambahkan PDF/gambar sendiri ke `data/` dan lanjutkan langkah berikut:

1. Buka folder workspace ini di VS Code.
2. Pilih **Terminal → New Terminal** (PowerShell).
3. Pilih interpreter lewat **Python: Select Interpreter** pada Command Palette, lalu pilih `.venv\Scripts\python.exe`.
4. Aktifkan environment dan instal dependency jika belum tersedia:

```powershell
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install -r requirements.txt
```

Jika PowerShell menolak aktivasi skrip, gunakan interpreter langsung tanpa mengubah kebijakan PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Jangan memakai Python global untuk instalasi project ini. Jika library sudah sesuai `requirements.txt`, instalasi ulang tidak diperlukan.

## Menjalankan dan menghasilkan QR

Dengan environment aktif:

```powershell
python main.py
```

Atau langsung dengan interpreter yang tersedia:

```powershell
.\.venv\Scripts\python.exe main.py
```

Program memeriksa `data/`, memilih IP, memeriksa ketersediaan alamat/port, menghasilkan QR, menampilkan hasil per file, lalu melayani HTTP pada port **8000**. Terminal tetap berjalan sampai **Ctrl+C** ditekan.

Contoh konfigurasi manual; ganti IP contoh dengan IPv4 Wi-Fi laptop:

```powershell
.\.venv\Scripts\python.exe main.py --host-ip 192.168.1.10 --port 8001
```

`--host-ip` digunakan untuk URL QR sekaligus antarmuka tempat server mendengarkan, sehingga harus merupakan alamat milik laptop ini. `0.0.0.0` bukan URL untuk HP dan ditolak. IPv6 belum didukung. `127.0.0.1` boleh untuk tes pada laptop, tetapi tidak dapat dipakai HP.

Untuk melihat opsi:

```powershell
.\.venv\Scripts\python.exe main.py --help
```

Jika folder kosong atau tidak ada format yang didukung, program menampilkan pesan jelas dan server tetap berjalan tanpa daftar file. Jika `data/` hilang, program berhenti dengan pesan error; buat kembali folder tersebut. Kegagalan menyimpan satu QR dilaporkan dan file lain tetap diproses. Jika semua QR gagal, server ditutup.

## Menambahkan file dan menemukan PNG

1. Salin PDF/JPG/JPEG/PNG ke `data/`, langsung di folder tersebut.
2. Hentikan server dengan Ctrl+C jika masih berjalan.
3. Jalankan kembali `main.py`.
4. Buka `output/` di Explorer VS Code untuk melihat PNG.

Contoh nama output:

| File sumber | QR PNG |
| --- | --- |
| `gambar 1.jpeg` | `gambar 1.jpeg_QR.png` |
| `NOTA MV. HT UNITE (HMC CRANE).pdf` | `NOTA MV. HT UNITE (HMC CRANE).pdf_QR.png` |
| `laporan.pdf` | `laporan.pdf_QR.png` |
| `laporan.jpg` | `laporan.jpg_QR.png` |

Ekstensi sumber sengaja dipertahankan agar nama dasar yang sama tidak bertabrakan. Menjalankan ulang memperbarui PNG dengan nama yang sama secara atomik. Output lama dari file yang telah dihapus/diubah namanya tidak dihapus otomatis; URL tersebut akan mengembalikan 404.

Nama file yang sangat panjang dapat melampaui batas nama/path Windows ketika ditambah `_QR.png`; kegagalan ini dilaporkan tanpa mengubah file sumber.

## Memindai melalui HP

1. Sambungkan HP dan laptop ke Wi-Fi/LAN yang sama.
2. Biarkan `main.py` berjalan pada laptop dan pastikan laptop tidak tidur.
3. Tampilkan PNG QR di layar laptop atau cetak dengan margin putih tetap utuh.
4. Pindai memakai kamera HP/fitur pemindai QR, lalu buka tautannya.
5. Browser akan menampilkan gambar atau PDF sesuai kemampuannya. Sebagian browser mungkin menawarkan unduhan PDF.

Contoh URL (alamat hanya ilustrasi):

```text
http://192.168.1.10:8000/gambar%201.jpeg
http://192.168.1.10:8000/NOTA%20MV.%20HT%20UNITE%20%28HMC%20CRANE%29.pdf
```

Alamat dasar seperti `http://192.168.1.10:8000/` sengaja mengembalikan **404**, karena directory listing dinonaktifkan. Gunakan URL lengkap yang dicetak terminal atau QR masing-masing file.

QR berhenti membuka file ketika server dimatikan, laptop terputus/tidur, atau IP/port berubah. Setelah IP/port berubah, jalankan ulang dan gunakan PNG terbaru; cetakan lama perlu diganti.

## Keamanan dan batas penggunaan

Siapa pun yang dapat menjangkau jaringan/server dan mengetahui URL dapat membuka file, karena MVP ini belum memiliki autentikasi. Letakkan hanya file yang ingin dibagikan di `data/`.

Server hanya menyediakan file reguler berformat yang diizinkan langsung di `data/`. Root dan direktori tidak ditampilkan, traversal POSIX/Windows ditolak, dan symlink tidak dilayani. Aplikasi hanya membaca sumber; tidak ada endpoint upload/edit/delete.

Gunakan pada jaringan lokal tepercaya. Server memakai HTTP tanpa TLS dan bukan layanan produksi/cloud. Aplikasi tidak membuka port router, membuat tunnel, atau mengatur Firewall secara otomatis. Jangan membuat port forwarding ke internet.

## Troubleshooting

**HP tidak bisa mengakses file**

- Coba URL lengkap yang dicetak terminal melalui browser laptop terlebih dahulu.
- Pastikan program masih berjalan dan laptop tidak tidur.
- Periksa HP dan laptop menggunakan jaringan yang sama; guest Wi-Fi/client isolation bisa melarang koneksi antarperangkat.
- Coba nonaktifkan VPN jika deteksi IP memilih antarmuka VPN. Jangan menonaktifkan perlindungan Firewall secara keseluruhan.
- Pakai `ipconfig` di terminal, lihat **IPv4 Address** pada adapter Wi-Fi/Ethernet aktif, lalu jalankan dengan `--host-ip` tersebut.

**IP berubah / QR lama gagal**

DHCP dapat mengganti IP laptop. Hentikan program, jalankan lagi dengan IP saat ini, dan gunakan/cetak ulang QR terbaru. Pada beberapa adapter aktif, deteksi otomatis bisa memilih IP yang tidak terjangkau HP; gunakan `--host-ip`.

**Windows Firewall memblokir**

Jika Windows meminta izin Python, izinkan akses untuk **Private networks** pada Wi-Fi tepercaya. Jika diperlukan, buka **Windows Security → Firewall & network protection → Allow an app through firewall**, lalu izinkan interpreter Python project pada jaringan privat. Pengaturan ini bisa memerlukan administrator. Pada komputer kantor, minta bantuan administrator. Jangan membuka akses publik atau port router.

**Port sedang digunakan / alamat tidak tersedia**

- Gunakan `--port 8001` atau hentikan proses lain yang memakai port tersebut.
- Untuk error alamat/IP tidak tersedia, pastikan `--host-ip` merupakan IPv4 aktif milik laptop.
- Jalankan ulang agar PNG memakai kombinasi IP/port yang baru.

**PNG tidak tersimpan**

Pastikan `output/` adalah folder biasa yang dapat ditulis, ruang disk cukup, dan nama/path tidak terlalu panjang. Program menampilkan error per file; jangan menghapus sumber untuk memperbaiki output.

## Pengujian lokal

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

Tes menggunakan server loopback dengan port sementara dan folder sementara di workspace; seluruhnya dibersihkan setelah tes. Pengujian mencakup sumber asli, PNG, payload URL ke encoder QR, ekstensi/nama keluaran, URL khusus, konten/MIME/HEAD, pembatasan akses, input tidak valid, error I/O, folder kosong, dan penghentian melalui SIGINT (sinyal yang ditangani Ctrl+C).

Pada clone baru dengan `data/` kosong, dua tes integrasi sumber asli dilewati. Tes lainnya menggunakan data sementara dan tetap berjalan. Tambahkan PDF/gambar ke `data/` untuk menjalankan seluruh tes.

Pengujian tersebut tidak membuktikan pemindaian kamera HP, akses dari perangkat lain, atau izin Windows Firewall. Hal-hal itu perlu diuji dengan HP nyata pada jaringan pengguna.

Referensi modul standar: [http.server Python 3.13](https://docs.python.org/3.13/library/http.server.html) dan [urllib.parse Python 3.13](https://docs.python.org/3.13/library/urllib.parse.html).
