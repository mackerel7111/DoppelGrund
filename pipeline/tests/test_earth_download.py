"""Plan B downloader: tile geometry and resume behaviour against a local HTTP server."""

from __future__ import annotations

import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from shapely.geometry import box

from doppelgrund.earth.download import download, known, land_tiles, record, run, tile_bbox

DATA = bytes(range(256)) * 4000  # about 1 MB


class Handler(BaseHTTPRequestHandler):
    drop_after: int | None = None  # first full GET sends only this many bytes, then closes
    reset_first: int = 0  # this many requests are dropped without any response

    def log_message(self, *a) -> None:  # silence
        pass

    def do_GET(self) -> None:
        if Handler.reset_first > 0:
            Handler.reset_first -= 1
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            return
        rng = self.headers.get("Range")
        start = int(rng.split("=")[1].split("-")[0]) if rng else 0
        end = int(rng.split("-")[1]) if rng and rng.split("-")[1] else len(DATA) - 1
        body = DATA[start : end + 1]
        self.send_response(206 if rng else 200)
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(DATA)}")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        limit = Handler.drop_after
        if limit is not None and start == 0 and end > 0:
            Handler.drop_after = None  # only the first big request is cut short
            body = body[:limit]
        self.wfile.write(body)
        self.wfile.flush()


@pytest.fixture()
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/f.bin"
    srv.shutdown()
    Handler.drop_after = None
    Handler.reset_first = 0


def test_tile_names_are_north_west_corners() -> None:
    assert tile_bbox("ETOPO_2022_v1_15s_N90W180_surface.tif") == (-180, 75, -165, 90)
    assert tile_bbox("ETOPO_2022_v1_15s_N00E000_surface.tif") == (0, -15, 15, 0)
    assert tile_bbox("ETOPO_2022_v1_15s_S75W015_surface.tif") == (-15, -90, 0, -75)
    with pytest.raises(ValueError):
        tile_bbox("other.tif")


def test_land_tiles_keep_only_tiles_touching_land() -> None:
    html = (
        'href="ETOPO_2022_v1_15s_N60E000_surface.tif" href="ETOPO_2022_v1_15s_N00W180_surface.tif"'
    )
    land = box(5, 50, 8, 55)  # inside the tile with NW corner 60N 0E (45-60N, 0-15E)
    assert land_tiles(html, land) == ["ETOPO_2022_v1_15s_N60E000_surface.tif"]


def test_download_completes_and_skips_a_finished_file(server: str, tmp_path: Path) -> None:
    dest = tmp_path / "a" / "f.bin"
    assert download(server, dest).read_bytes() == DATA
    mtime = dest.stat().st_mtime_ns
    download(server, dest)
    assert dest.stat().st_mtime_ns == mtime  # not fetched again


def test_download_resumes_a_cut_connection_and_a_leftover_part_file(
    server: str, tmp_path: Path
) -> None:
    Handler.drop_after = 300_000  # server hangs up after 300 kB
    dest = tmp_path / "f.bin"
    assert download(server, dest, tries=4).read_bytes() == DATA
    leftover = tmp_path / "g.bin"
    (tmp_path / "g.bin.part").write_bytes(DATA[:123_456])  # an earlier interrupted run
    assert download(server, leftover).read_bytes() == DATA
    assert not (tmp_path / "g.bin.part").exists()


def test_manifest_records_finished_files_and_run_skips_them(server: str, tmp_path: Path) -> None:
    m = tmp_path / "MANIFEST.csv"
    dest = tmp_path / "f.bin"
    lines: list[str] = []
    run([(server, dest)], m, workers=1, log=lines.append)
    assert known(m) == {"f.bin"} and "1 of 1" in lines[0]
    lines.clear()
    run([(server, dest)], m, workers=1, log=lines.append)
    assert lines == ["0 of 1 files to fetch"]
    record(m, server, dest)  # appending again must keep a single header
    assert m.read_text().count("file,bytes,sha256,url") == 1


def test_earthdata_jobs_dedupe_and_keep_only_hdf_links(monkeypatch, tmp_path: Path) -> None:
    import sys
    import types

    from doppelgrund.earth.download import earthdata_jobs

    class G:
        def __init__(self, name: str) -> None:
            self.name = name

        def data_links(self) -> list[str]:
            return [f"https://x/{self.name}.xml", f"https://x/{self.name}.hdf"]

    calls = []

    def search_data(short_name: str, version: str, temporal: tuple[str, str]) -> list[G]:
        calls.append((short_name, version, temporal))
        return [G("b"), G("a"), G("a")]  # a duplicate granule must not be fetched twice

    monkeypatch.setitem(sys.modules, "earthaccess", types.SimpleNamespace(search_data=search_data))
    jobs = earthdata_jobs(tmp_path, {"MOD11C2": ("061", [("2010-01-01", "2010-12-31")])})
    assert calls == [("MOD11C2", "061", ("2010-01-01", "2010-12-31"))]
    assert jobs == [
        ("https://x/a.hdf", tmp_path / "modis" / "MOD11C2" / "a.hdf"),
        ("https://x/b.hdf", tmp_path / "modis" / "MOD11C2" / "b.hdf"),
    ]


def test_a_connection_reset_on_the_size_lookup_is_retried(
    server: str, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("doppelgrund.earth.download.time.sleep", lambda s: None)
    Handler.reset_first = (
        2  # the first two requests die before any response (this used to crash the run)
    )
    assert download(server, tmp_path / "f.bin", tries=5).read_bytes() == DATA


def test_one_failing_file_does_not_stop_the_others(
    server: str, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("doppelgrund.earth.download.time.sleep", lambda s: None)
    jobs = [
        ("http://127.0.0.1:9/unreachable.bin", tmp_path / "bad.bin"),
        (server, tmp_path / "ok.bin"),
    ]
    with pytest.raises(OSError, match="1 file"):
        run(jobs, tmp_path / "MANIFEST.csv", workers=2, log=lambda m: None)
    assert (tmp_path / "ok.bin").read_bytes() == DATA and known(tmp_path / "MANIFEST.csv") == {
        "ok.bin"
    }
