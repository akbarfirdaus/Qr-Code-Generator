# Product Requirements Document — QR Code File Generator

Versi: 1.0 · Status: MVP · Tanggal: 13 Oktober 2026

## 1. Product Overview

QR Code File Generator adalah aplikasi terminal Python yang menghasilkan QR PNG untuk PDF dan gambar, lalu menyediakan file melalui local HTTP file server. Produk dirancang sebagai MVP sederhana untuk berbagi dokumen di jaringan lokal, tanpa cloud storage, database, login, atau framework web.

## 2. Background

Pengguna sudah memiliki file lokal di folder `data/` dan ingin membuka file tersebut dari HP tanpa mengirim satu per satu. Workspace menyediakan Python 3.13 dalam `.venv/`, serta qrcode dan Pillow.

## 3. Problem Statement

Path Windows tidak dapat digunakan HP sebagai tautan. File lokal memerlukan URL HTTP yang dapat dijangkau pada LAN. Penamaan dengan spasi/karakter khusus, perubahan IP, dan akses ke folder di luar sumber harus ditangani dengan benar.

## 4. Product Goals

- Menghasilkan satu QR yang mudah dicetak untuk setiap file yang didukung.
- Membuka file dari HP pada jaringan yang sama selama server aktif.
- Menjaga sumber tetap utuh dan membatasi layanan ke `data/`.
- Menyediakan alur terminal serta dokumentasi yang mudah dipahami pemula.

## 5. Target Users

Pengguna individu/staf operasional yang membagikan PDF, nota, atau gambar pada jaringan Wi-Fi/LAN tepercaya dengan laptop Windows dan HP berkamera.

## 6. Scope

**Termasuk:** pemindaian file langsung di `data/`, format PDF/JPG/JPEG/PNG, URL encoding, QR PNG, deteksi IPv4, konfigurasi IP/port, server HTTP lokal, dokumentasi, serta pengujian otomatis.

**Di luar MVP:** cloud/public hosting, database, autentikasi, TLS, GUI, upload, pengawasan folder otomatis, subfolder rekursif, IPv6, short URL, analytics, serta modifikasi sumber.

## 7. Functional Requirements

| ID | Kebutuhan |
| --- | --- |
| FR-01 | Membaca file biasa langsung di `data/`; ekstensi tidak peka huruf besar/kecil; format lain/subfolder/symlink diabaikan. |
| FR-02 | Membuat URL HTTP per file menggunakan IPv4 dan port server; nama file di-encode UTF-8 dengan percent encoding. |
| FR-03 | Mendeteksi IP antarmuka LAN tanpa membutuhkan internet; memberikan error dengan petunjuk `--host-ip` jika gagal. |
| FR-04 | Mendukung `--host-ip` dan `--port`; port default 8000; input tidak valid ditolak. |
| FR-05 | Membuat `output/` otomatis dan menyimpan `<nama lengkap sumber>_QR.png`; ekstensi sumber mencegah benturan nama dasar. |
| FR-06 | Menggunakan QR hitam-putih, border 4 modul, skala 16 piksel/modul, koreksi kesalahan M, dan metadata cetak 300 DPI. |
| FR-07 | Menampilkan nama sumber, path PNG, URL, jumlah berhasil/gagal, serta alamat server. |
| FR-08 | Menggunakan server HTTP standar Python pada IP pilihan; mendukung GET/HEAD, MIME yang tepat, dan tampilan inline. |
| FR-09 | Tidak menampilkan daftar direktori; menolak traversal, symlink, file tidak didukung, dan file di luar `data/`. |
| FR-10 | Tetap berjalan sampai Ctrl+C dan menutup socket dengan baik. |
| FR-11 | Folder kosong menghasilkan pesan jelas dan server tetap berjalan; folder hilang/masalah I/O ditangani tanpa traceback untuk error operasional. |
| FR-12 | File baru memperoleh QR setelah program dijalankan ulang; perubahan IP/port memperbarui PNG saat dijalankan ulang. |

## 8. Non-Functional Requirements

- **Kesederhanaan:** satu modul aplikasi dan satu modul tes; dependency eksternal terbatas pada qrcode/Pillow.
- **Keamanan sumber:** membaca file tanpa mengubah, menghapus, memindahkan, atau mengganti nama.
- **Keandalan:** kegagalan satu PNG tidak menggagalkan file lain; PNG ditulis melalui file sementara lalu diganti secara atomik.
- **Kegunaan:** terminal, error, README, dan petunjuk berbahasa Indonesia.
- **Kompatibilitas:** Python 3.13, Windows, browser HP yang mendukung gambar/PDF.
- **Operasional:** tidak membutuhkan internet setelah dependency tersedia; tidak mengubah Firewall/router.
- **Performa:** HTTP memakai thread dan menyalin konten bertahap; kebutuhan ditujukan untuk penggunaan lokal ringan, tanpa SLA/beban produksi.

## 9. System Architecture

```text
data/ → pemilihan file → URL HTTP ter-encode → qrcode/Pillow → output/*.png
  ↑
HTTP server Python ← browser HP ← hasil pemindaian QR
```

URL mengarah langsung ke nama file di root layanan. Handler memvalidasi path dan format, memastikan lokasi hasil resolusi tetap di `data/`, membuka file read-only, lalu mengirim konten dengan MIME yang sesuai. IP pilihan dipakai pada URL sekaligus bind server. Root layanan mengembalikan 404 dan tidak menampilkan isi folder.

## 10. User Flow

1. Pengguna menyalin PDF/gambar ke `data/`.
2. Pengguna menjalankan program dengan interpreter `.venv`.
3. Program memeriksa sumber, mendeteksi/menerima IP, dan memeriksa bind alamat/port.
4. Program membuat PNG QR dan menampilkan hasil.
5. Server menunggu akses pada LAN.
6. HP pada jaringan yang sama memindai QR dan membuka file.
7. Pengguna menekan Ctrl+C untuk menutup server.
8. Setelah menambah file/mengubah jaringan, pengguna menjalankan ulang dan memakai QR terbaru.

## 11. Technology Stack

| Komponen | Teknologi |
| --- | --- |
| Runtime | Python 3.13 dalam virtual environment yang tersedia |
| QR | qrcode 8.2 |
| PNG | Pillow 12.3.0 |
| HTTP | http.server.ThreadingHTTPServer dan BaseHTTPRequestHandler |
| Jaringan/URL | socket, ipaddress, urllib.parse |
| File/CLI | pathlib, argparse, tempfile, shutil, os |
| Pengujian | unittest, unittest.mock, http.client, subprocess; Pillow untuk validasi PNG |

## 12. File Structure

```text
Qr qode/
├── .venv/
├── data/
├── output/
├── main.py
├── test_main.py
├── requirements.txt
├── README.md
├── PRD.md
└── .gitignore
```

## 13. Acceptance Criteria

- Semua PDF/JPEG awal di `data/` menghasilkan satu PNG dan hash sumber tetap sama.
- PNG valid, berwarna hitam-putih, memiliki margin, dan encoder menerima URL HTTP yang sesuai.
- `laporan.pdf` dan `laporan.jpg` menghasilkan PNG berbeda.
- URL file dengan spasi, tanda kurung, Unicode, dan karakter khusus mengembalikan konten yang benar.
- Respons sukses memiliki MIME, panjang konten, dan header inline yang tepat; HEAD tidak mengirim body.
- Root/subfolder tidak menampilkan directory listing; traversal, format terlarang, dan akses di luar `data/` gagal.
- Folder kosong tidak crash dan memberikan pesan jelas.
- IP/port tidak valid atau bind/I/O gagal menghasilkan pesan yang dapat ditindaklanjuti.
- Penghentian SIGINT/Ctrl+C menutup server dan keluar dengan baik.
- Uji kamera HP dan akses lintas perangkat dicatat sebagai validasi manual yang belum dilakukan oleh tes lokal.

## 14. Limitations

- QR berisi URL, bukan isi file; laptop/server harus tetap aktif.
- HP harus dapat menjangkau IP laptop pada LAN; guest isolation, VPN, Firewall, dan perubahan DHCP dapat menghambat akses.
- Tanpa autentikasi: siapa pun yang dapat mengakses jaringan/server dan URL dapat membuka file.
- HTTP tanpa enkripsi; penggunaan dibatasi pada jaringan tepercaya, bukan layanan publik.
- Deteksi otomatis dapat memilih antarmuka yang salah pada laptop dengan beberapa adapter; gunakan override IP.
- Format ditentukan dari ekstensi, bukan validasi isi file.
- File sumber sangat panjang dapat melampaui batas nama output Windows.
- Output lama tidak dihapus otomatis; QR lama tidak mengikuti perubahan IP/port/nama file.
- Tidak menyediakan optimasi streaming/range PDF besar, pengaturan router, atau pembaruan folder otomatis.

## 15. Future Improvements

- Pemilihan antarmuka jaringan secara interaktif.
- Opsi ukuran QR untuk kebutuhan cetak khusus.
- Indeks lokal yang dipilih pengguna dan ekspor daftar URL.
- Pengawasan folder otomatis dan pengelolaan output lama secara eksplisit.
- Dukungan range request untuk PDF besar.
- Autentikasi/TLS jika kebutuhan berkembang, dengan desain keamanan tersendiri.
