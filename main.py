"""QR Code File Generator: bagikan PDF/gambar melalui jaringan lokal."""

from __future__ import annotations

import argparse
import ipaddress
import os
import shutil
import socket
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

try:
    import qrcode
    from qrcode.exceptions import DataOverflowError
    from qrcode.image.pil import PilImage
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Dependency belum lengkap. Aktifkan .venv lalu jalankan: "
        "python -m pip install -r requirements.txt"
    ) from exc

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "output"
SUPPORTED_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def parse_host_ip(value: str) -> str:
    """Terima IPv4 antarmuka laptop; localhost boleh untuk pengujian."""
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as exc:
        raise argparse.ArgumentTypeError("Gunakan alamat IPv4, misalnya 192.168.1.10.") from exc
    if address.is_unspecified or address.is_multicast or address.is_reserved:
        raise argparse.ArgumentTypeError("Gunakan IPv4 laptop, bukan alamat wildcard/broadcast.")
    return str(address)


def parse_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Port harus berupa angka 1 sampai 65535.") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port harus antara 1 dan 65535.")
    return port


def detect_lan_ip() -> str:
    """Cari antarmuka rute default tanpa mengirim paket atau membutuhkan internet."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            connection.settimeout(1)
            # TEST-NET: connect UDP hanya memilih rute; tidak ada send/sendto.
            connection.connect(("192.0.2.1", 80))
            address = connection.getsockname()[0]
            if not ipaddress.IPv4Address(address).is_loopback:
                return parse_host_ip(address)
    except (OSError, argparse.ArgumentTypeError):
        pass

    try:
        candidates = socket.getaddrinfo(
            socket.gethostname(), None, socket.AF_INET, socket.SOCK_DGRAM
        )
        for *_, socket_address in candidates:
            address = ipaddress.IPv4Address(socket_address[0])
            if not address.is_loopback and not address.is_link_local:
                try:
                    return parse_host_ip(str(address))
                except argparse.ArgumentTypeError:
                    continue
    except OSError:
        pass
    raise RuntimeError(
        "IP LAN tidak dapat dideteksi. Lihat IPv4 Wi-Fi melalui ipconfig, lalu "
        "jalankan python main.py --host-ip 192.168.1.10 (sesuaikan IP laptop)."
    )


def discover_files(data_dir: Path) -> list[Path]:
    """Hanya file biasa langsung di data/; subfolder dan symlink diabaikan."""
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Folder data tidak ditemukan: {data_dir}")
    root = data_dir.resolve(strict=True)
    return sorted(
        (
            path
            for path in root.iterdir()
            if path.suffix.lower() in SUPPORTED_TYPES
            and not path.is_symlink()
            and path.is_file()
            and path.resolve(strict=True).parent == root
        ),
        key=lambda path: path.name.casefold(),
    )


def build_file_url(host_ip: str, port: int, filename: str) -> str:
    return f"http://{host_ip}:{port}/{quote(filename, safe='')}"


def generate_qr_codes(
    files: list[Path], output_dir: Path, host_ip: str, port: int
) -> tuple[int, int]:
    """Simpan PNG secara atomik; kegagalan satu file tidak menghentikan file lain."""
    if output_dir.is_symlink() or output_dir.is_junction():
        raise OSError("Folder output tidak boleh berupa symlink/junction.")
    output_dir.mkdir(parents=True, exist_ok=True)
    successful = failed = 0
    for source in files:
        # Ekstensi sumber dipertahankan agar laporan.pdf dan laporan.jpg unik.
        destination = output_dir / f"{source.name}_QR.png"
        temporary = None
        try:
            url = build_file_url(host_ip, port, source.name)
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=16,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)
            image = qr.make_image(
                image_factory=PilImage, fill_color="black", back_color="white"
            )
            with tempfile.NamedTemporaryFile(
                dir=output_dir, prefix=".qr-", suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                image.save(stream, format="PNG", dpi=(300, 300))
            temporary.replace(destination)
            successful += 1
            print(f"[OK] {source.name}\n     PNG: {destination}\n     URL: {url}")
        except (OSError, ValueError, DataOverflowError) as exc:
            failed += 1
            print(f"[GAGAL] {source.name}: {exc}", file=sys.stderr)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as exc:
                    print(f"Peringatan: gagal membersihkan {temporary}: {exc}", file=sys.stderr)
    return successful, failed


def make_file_handler(data_dir: Path) -> type[BaseHTTPRequestHandler]:
    root = data_dir.resolve(strict=True)

    class FileHandler(BaseHTTPRequestHandler):
        server_version = "QRFileServer/1.0"
        sys_version = ""
        timeout = 15

        def do_GET(self) -> None:
            self.send_file(include_body=True)

        def do_HEAD(self) -> None:
            self.send_file(include_body=False)

        def send_file(self, include_body: bool) -> None:
            try:
                parsed = urlsplit(self.path)
                if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
                    self.send_error(400, "URL tidak valid")
                    return
                name = unquote(parsed.path[1:], encoding="utf-8", errors="strict")
            except (ValueError, UnicodeError):
                self.send_error(400, "URL tidak valid")
                return

            if not name:
                self.send_error(404, "Gunakan URL file dari QR Code; daftar folder dinonaktifkan")
                return
            # Tolak traversal POSIX/Windows, drive/ADS Windows, dan karakter kontrol.
            if (
                name in {".", ".."}
                or any(character in name for character in "/\\:")
                or any(ord(character) < 32 or ord(character) == 127 for character in name)
            ):
                self.send_error(403, "Akses path ditolak")
                return
            mime_type = SUPPORTED_TYPES.get(Path(name).suffix.lower())
            if mime_type is None:
                self.send_error(404, "Format file tidak diizinkan")
                return

            candidate = root / name
            try:
                if candidate.is_symlink():
                    self.send_error(403, "Symlink tidak diizinkan")
                    return
                resolved = candidate.resolve(strict=True)
                if resolved.parent != root:
                    self.send_error(403, "Akses di luar data ditolak")
                    return
                if not resolved.is_file():
                    self.send_error(404, "File tidak ditemukan")
                    return
                stream = resolved.open("rb")
            except FileNotFoundError:
                self.send_error(404, "File tidak ditemukan")
                return
            except PermissionError:
                self.send_error(403, "File tidak dapat dibaca")
                return
            except (OSError, ValueError):
                self.send_error(500, "Gagal membaca file")
                return

            try:
                with stream:
                    info = os.fstat(stream.fileno())
                    self.send_response(200)
                    self.send_header("Content-Type", mime_type)
                    self.send_header("Content-Length", str(info.st_size))
                    self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{quote(name, safe='')}")
                    self.send_header("Last-Modified", self.date_time_string(info.st_mtime))
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    if include_body:
                        shutil.copyfileobj(stream, self.wfile)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # Browser/HP menutup koneksi sebelum transfer selesai.
            except OSError as exc:
                self.log_error("Transfer file gagal: %s", exc)

    return FileHandler


def create_server(data_dir: Path, host_ip: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host_ip, port), make_file_handler(data_dir))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Buat QR Code PDF/gambar lalu jalankan server file lokal."
    )
    parser.add_argument("--host-ip", type=parse_host_ip, help="IPv4 Wi-Fi/LAN laptop (default: deteksi otomatis)")
    parser.add_argument("--port", type=parse_port, default=8000, help="Port HTTP, default: 8000")
    args = parser.parse_args(argv)

    try:
        files = discover_files(DATA_DIR)
        host_ip = args.host_ip or detect_lan_ip()
        print(f"QR Code File Generator\nFolder data: {DATA_DIR}\nIP server: {host_ip}")
        if ipaddress.IPv4Address(host_ip).is_loopback:
            print("Peringatan: IP localhost hanya dapat diakses laptop ini. Gunakan IP Wi-Fi untuk HP.")
        # Periksa bind sebelum menulis QR agar IP/port yang tidak tersedia terdeteksi awal.
        with create_server(DATA_DIR, host_ip, args.port) as server:
            successful, failed = generate_qr_codes(files, OUTPUT_DIR, host_ip, args.port)
            print(f"\nHasil: {successful} berhasil, {failed} gagal, {len(files)} file didukung.")
            if not files:
                print("Folder data kosong atau tidak berisi PDF/JPG/JPEG/PNG. Tambahkan file lalu jalankan ulang.")
            elif successful == 0:
                print("Tidak ada QR yang berhasil dibuat. Periksa pesan error dan izin output.", file=sys.stderr)
                return 1
            print(f"\nServer aktif: http://{host_ip}:{args.port}")
            print("Buka URL file atau pindai QR; alamat dasar tidak menampilkan daftar folder.")
            print("HP dan laptop harus berada pada jaringan yang sama. Tekan Ctrl+C untuk berhenti.")
            server.serve_forever(poll_interval=0.25)
        return 1 if failed else 0
    except KeyboardInterrupt:
        print("\nServer dihentikan. Selesai.")
        return 0
    except (OSError, RuntimeError) as exc:
        print(
            f"Error: {exc}\nPeriksa folder/izin file, IPv4 laptop (--host-ip), dan port (--port). "
            "Jika port terpakai, gunakan --port 8001.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
