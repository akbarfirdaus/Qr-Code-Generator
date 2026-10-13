"""Pengujian lokal: tidak mengubah sumber dan tidak membutuhkan perangkat HP."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.client
import io
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

import main


@contextlib.contextmanager
def running_server(data_dir: Path):
    server = main.create_server(data_dir, "127.0.0.1", 0)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
    )
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(port: int, path: str, method: str = "GET"):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


class TemporaryWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix=".qr-test-", dir=main.PROJECT_DIR
        )
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.output = self.root / "output"


class OriginalFilesTests(TemporaryWorkspaceTest):
    def setUp(self):
        super().setUp()
        self.sources = main.discover_files(main.DATA_DIR)
        if not self.sources:
            self.skipTest("Tambahkan PDF/gambar ke data/ untuk tes integrasi sumber asli.")

    def test_all_real_sources_generate_valid_qr_without_source_changes(self):
        sources = self.sources
        before = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources
        }
        original_add_data = main.qrcode.QRCode.add_data
        with (
            contextlib.redirect_stdout(io.StringIO()),
            mock.patch.object(
                main.qrcode.QRCode,
                "add_data",
                autospec=True,
                side_effect=original_add_data,
            ) as add_data,
        ):
            result = main.generate_qr_codes(sources, self.output, "192.168.1.10", 8000)
        self.assertEqual(result, (len(sources), 0))
        self.assertEqual(
            [call.args[1] for call in add_data.call_args_list],
            [main.build_file_url("192.168.1.10", 8000, source.name) for source in sources],
        )
        self.assertEqual(len(list(self.output.glob("*.png"))), len(sources))
        self.assertFalse(list(self.output.glob("*.tmp")))
        for source in sources:
            with self.subTest(file=source.name):
                destination = self.output / f"{source.name}_QR.png"
                with Image.open(destination) as image:
                    image.load()
                    self.assertEqual(image.format, "PNG")
                    self.assertEqual(image.width, image.height)
                    self.assertGreaterEqual(image.width, 500)
                    self.assertAlmostEqual(image.info["dpi"][0], 300, delta=1)
                    self.assertEqual(image.convert("L").getextrema(), (0, 255))
                    # Quiet zone empat modul x 16 px di sisi kiri.
                    self.assertEqual(
                        image.crop((0, 0, 64, image.height)).convert("L").getextrema(),
                        (255, 255),
                    )
        after = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in main.discover_files(main.DATA_DIR)
        }
        self.assertEqual(before, after)

    def test_original_file_endpoints_return_exact_content_and_mime(self):
        with running_server(main.DATA_DIR) as port:
            for source in self.sources:
                with self.subTest(file=source.name):
                    url = main.build_file_url("127.0.0.1", port, source.name)
                    path = url.split(f":{port}", 1)[1]
                    status, headers, body = request(port, path)
                    self.assertEqual(status, 200)
                    self.assertEqual(body, source.read_bytes())
                    self.assertEqual(headers["Content-Type"], main.SUPPORTED_TYPES[source.suffix.lower()])
                    self.assertEqual(int(headers["Content-Length"]), source.stat().st_size)


class GenerationTests(TemporaryWorkspaceTest):
    def test_supported_formats_and_same_stem_do_not_collide(self):
        names = ["laporan.pdf", "laporan.jpg", "laporan.JPEG", "laporan.PNG"]
        for name in names + ["ignore.txt"]:
            (self.data / name).write_bytes(b"test")
        (self.data / "folder.pdf").mkdir()
        (self.data / "folder.pdf" / "nested.jpg").write_bytes(b"test")
        files = main.discover_files(self.data)
        self.assertEqual({file.name for file in files}, set(names))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                main.generate_qr_codes(files, self.output, "127.0.0.1", 8000), (4, 0)
            )
        self.assertEqual(
            {path.name for path in self.output.iterdir()},
            {f"{name}_QR.png" for name in names},
        )

    def test_io_error_is_reported_and_other_files_continue(self):
        for name in ["a.pdf", "b.jpg"]:
            (self.data / name).write_bytes(b"test")
        original_save = main.PilImage.save
        calls = 0

        def failing_first_save(image, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("disk penuh (simulasi)")
            return original_save(image, *args, **kwargs)

        errors = io.StringIO()
        with (
            mock.patch.object(main.PilImage, "save", new=failing_first_save),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(errors),
        ):
            result = main.generate_qr_codes(
                main.discover_files(self.data), self.output, "127.0.0.1", 8000
            )
        self.assertEqual(result, (1, 1))
        self.assertIn("disk penuh", errors.getvalue())
        self.assertTrue((self.output / "b.jpg_QR.png").is_file())
        self.assertFalse(list(self.output.glob("*.tmp")))

    def test_repeated_generation_replaces_png_with_new_url(self):
        source = self.data / "a.pdf"
        source.write_bytes(b"test")
        with contextlib.redirect_stdout(io.StringIO()):
            main.generate_qr_codes([source], self.output, "192.168.1.10", 8000)
            first = (self.output / "a.pdf_QR.png").read_bytes()
            main.generate_qr_codes([source], self.output, "192.168.1.20", 8001)
        self.assertNotEqual(first, (self.output / "a.pdf_QR.png").read_bytes())
        self.assertEqual(source.read_bytes(), b"test")

    def test_url_encoding_of_reserved_and_unicode_characters(self):
        self.assertEqual(
            main.build_file_url("192.168.1.10", 8000, "café #50% + (uji).pdf"),
            "http://192.168.1.10:8000/caf%C3%A9%20%2350%25%20%2B%20%28uji%29.pdf",
        )


class ServerSecurityTests(TemporaryWorkspaceTest):
    def setUp(self):
        super().setUp()
        self.filename = "café #50% + (uji).PDF"
        self.content = b"%PDF-1.7\nlocal-test\n%%EOF"
        (self.data / self.filename).write_bytes(self.content)
        (self.data / "ignore.txt").write_bytes(b"not-allowed")
        (self.data / "folder").mkdir()
        (self.data / "folder" / "nested.pdf").write_bytes(b"nested")
        (self.root / "outside.pdf").write_bytes(b"secret-outside-data")

    def test_encoded_filename_and_query_are_supported(self):
        with running_server(self.data) as port:
            path = "/" + main.quote(self.filename, safe="") + "?preview=1"
            status, headers, body = request(port, path)
        self.assertEqual(status, 200)
        self.assertEqual(body, self.content)
        self.assertEqual(headers["Content-Type"], "application/pdf")
        self.assertTrue(headers["Content-Disposition"].startswith("inline;"))
        self.assertIn("%C3%A9", headers["Content-Disposition"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_head_returns_headers_without_body(self):
        with running_server(self.data) as port:
            status, headers, body = request(port, "/" + main.quote(self.filename), "HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(int(headers["Content-Length"]), len(self.content))
        self.assertEqual(headers["Content-Type"], "application/pdf")
        self.assertEqual(body, b"")

    def test_directory_listing_and_unsupported_files_are_denied(self):
        with running_server(self.data) as port:
            for path in ["/", "/?x=1", "/folder/", "/folder/nested.pdf", "/ignore.txt", "/main.py"]:
                with self.subTest(path=path):
                    status, _, body = request(port, path)
                    self.assertIn(status, (403, 404))
                    self.assertNotIn(b"Directory listing", body)
                    self.assertNotIn(b"not-allowed", body)

    def test_traversal_and_windows_paths_are_denied(self):
        paths = [
            "/../outside.pdf",
            "/%2e%2e/outside.pdf",
            "/%2E%2E%5coutside.pdf",
            "/..%2foutside.pdf",
            "/%2f..%2foutside.pdf",
            "/C:%5coutside.pdf",
            "/foo.pdf:alternate",
            "/%00foo.pdf",
            "/%252e%252e%252foutside.pdf",
        ]
        with running_server(self.data) as port:
            for path in paths:
                with self.subTest(path=path):
                    status, _, body = request(port, path)
                    self.assertIn(status, (400, 403, 404))
                    self.assertNotIn(b"secret-outside-data", body)

    def test_missing_and_invalid_utf8_paths_are_rejected(self):
        with running_server(self.data) as port:
            self.assertEqual(request(port, "/missing.pdf")[0], 404)
            self.assertEqual(request(port, "/%ff.pdf")[0], 400)

    def test_symlink_is_denied_before_open(self):
        # Simulasi status symlink agar tes tidak memerlukan hak admin Windows.
        with running_server(self.data) as port:
            with mock.patch.object(Path, "is_symlink", return_value=True):
                self.assertEqual(
                    request(port, "/" + main.quote(self.filename, safe=""))[0], 403
                )

    def test_post_cannot_modify_source(self):
        with running_server(self.data) as port:
            status, _, _ = request(port, "/" + main.quote(self.filename, safe=""), "POST")
        self.assertEqual(status, 501)
        self.assertEqual((self.data / self.filename).read_bytes(), self.content)


class CommandLineTests(TemporaryWorkspaceTest):
    def test_empty_folder_stays_usable_and_interrupt_closes_socket(self):
        server = main.create_server(self.data, "127.0.0.1", 0)
        output = io.StringIO()
        with (
            mock.patch.object(main, "DATA_DIR", self.data),
            mock.patch.object(main, "OUTPUT_DIR", self.output),
            mock.patch.object(main, "create_server", return_value=server),
            mock.patch.object(server, "serve_forever", side_effect=KeyboardInterrupt),
            contextlib.redirect_stdout(output),
        ):
            status = main.main(["--host-ip", "127.0.0.1"])
        self.assertEqual(status, 0)
        self.assertIn("Folder data kosong", output.getvalue())
        self.assertIn("Server dihentikan", output.getvalue())
        self.assertEqual(server.socket.fileno(), -1)
        self.assertTrue(self.output.is_dir())

    def test_missing_folder_returns_clear_error(self):
        with (
            mock.patch.object(main, "DATA_DIR", self.root / "missing"),
            contextlib.redirect_stderr(io.StringIO()) as errors,
        ):
            status = main.main(["--host-ip", "127.0.0.1"])
        self.assertEqual(status, 1)
        self.assertIn("Folder data tidak ditemukan", errors.getvalue())

    def test_invalid_arguments_are_rejected(self):
        arguments = [
            ["--port", "0"], ["--port", "65536"], ["--port", "abc"],
            ["--host-ip", "not-ip"], ["--host-ip", "0.0.0.0"],
            ["--host-ip", "255.255.255.255"], ["--host-ip", "224.0.0.1"],
        ]
        for args in arguments:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main.main(args)
                self.assertEqual(error.exception.code, 2)

    def test_unavailable_bind_does_not_generate_unusable_qr(self):
        with (
            mock.patch.object(main, "DATA_DIR", self.data),
            mock.patch.object(main, "OUTPUT_DIR", self.output),
            mock.patch.object(main, "create_server", side_effect=OSError("port terpakai")),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()) as errors,
        ):
            status = main.main(["--host-ip", "127.0.0.1"])
        self.assertEqual(status, 1)
        self.assertIn("port terpakai", errors.getvalue())
        self.assertFalse(self.output.exists())

    def test_real_server_subprocess_stops_cleanly_on_sigint(self):
        (self.data / "uji.pdf").write_bytes(b"%PDF-1.7\n%%EOF")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        script = """
import http.client
import signal
import sys
import threading
import time
from pathlib import Path
import main

main.DATA_DIR = Path(sys.argv[1])
main.OUTPUT_DIR = Path(sys.argv[2])
port = int(sys.argv[3])

def interrupt_when_serving():
    for _ in range(100):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.2)
        try:
            connection.request("GET", "/uji.pdf")
            response = connection.getresponse()
            response.read()
            if response.status == 200:
                signal.raise_signal(signal.SIGINT)
                return
        except OSError:
            time.sleep(0.05)
        finally:
            connection.close()

threading.Thread(target=interrupt_when_serving, daemon=True).start()
raise SystemExit(main.main(["--host-ip", "127.0.0.1", "--port", str(port)]))
"""
        completed = subprocess.run(
            [sys.executable, "-u", "-c", script, str(self.data), str(self.output), str(port)],
            cwd=main.PROJECT_DIR,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("Server aktif:", completed.stdout)
        self.assertIn("Server dihentikan", completed.stdout)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertTrue((self.output / "uji.pdf_QR.png").is_file())
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=0.2)


class NetworkTests(unittest.TestCase):
    def test_route_detection_uses_udp_without_sending_payload(self):
        with mock.patch.object(main.socket, "socket") as socket_factory:
            connection = socket_factory.return_value.__enter__.return_value
            connection.getsockname.return_value = ("192.168.1.10", 12345)
            self.assertEqual(main.detect_lan_ip(), "192.168.1.10")
            connection.send.assert_not_called()
            connection.sendto.assert_not_called()

    def test_hostname_fallback_skips_loopback(self):
        candidates = [
            (socket.AF_INET, socket.SOCK_DGRAM, 17, "", ("127.0.0.1", 0)),
            (socket.AF_INET, socket.SOCK_DGRAM, 17, "", ("192.168.1.20", 0)),
        ]
        with (
            mock.patch.object(main.socket, "socket", side_effect=OSError),
            mock.patch.object(main.socket, "getaddrinfo", return_value=candidates),
        ):
            self.assertEqual(main.detect_lan_ip(), "192.168.1.20")

    def test_detection_failure_explains_host_ip_override(self):
        with (
            mock.patch.object(main.socket, "socket", side_effect=OSError),
            mock.patch.object(main.socket, "getaddrinfo", side_effect=OSError),
        ):
            with self.assertRaisesRegex(RuntimeError, "--host-ip"):
                main.detect_lan_ip()


if __name__ == "__main__":
    unittest.main()
