"""Serve configured local sites as read-only files within their resolved roots."""
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit

from collect import load_config


class StaticSiteHandlerMixin:
    def local_host(self):
        port = self.server.server_port
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self.send_error(403, "Host must name this loopback server")
            return False
        return True

    def site_path(self):
        path = urlsplit(self.path).path
        # Decode nested encodings too, so an encoded traversal never becomes a filename.
        for _ in range(8):
            decoded = unquote(path)
            if decoded == path:
                break
            path = decoded
        for site in load_config().get("sites", []):
            prefix = "/" + site["mount"].strip("/")
            if path == prefix or path.startswith(prefix + "/"):
                return site, path[len(prefix):].lstrip("/")
        return None

    def serve_site(self, match):
        site, relative = match
        if ("\\" in relative or "\x00" in relative or "%" in relative
                or any(part in (".", "..") for part in relative.split("/"))):
            self.send_error(403, "Site path refused")
            return
        try:
            root = Path(site["dir"]).expanduser().resolve()
            path = (root / (relative or "index.html")).resolve()
            if not path.is_relative_to(root):
                self.send_error(403, "Site path refused")
                return
            if not path.is_file():
                self.send_error(404, "Site file not found")
                return
            with path.open("rb") as stream:
                self.send_response(200)
                kind = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
                if kind.startswith("text/") or kind in ("application/json", "application/javascript", "image/svg+xml"):
                    kind += "; charset=utf-8"
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(path.stat().st_size))
                self.end_headers()
                if self.command != "HEAD":
                    self.copyfile(stream, self.wfile)
        except (OSError, ValueError):
            self.send_error(404, "Site file not found")

    def do_GET(self):
        if not self.local_host():
            return
        match = self.site_path()
        if match is not None:
            self.serve_site(match)
        else:
            super().do_GET()

    def do_HEAD(self):
        if not self.local_host():
            return
        match = self.site_path()
        if match is not None:
            self.serve_site(match)
        else:
            super().do_HEAD()

    def do_POST(self):
        if self.site_path() is not None:
            self.send_error(405, "Sites are read-only")
        else:
            super().do_POST()
