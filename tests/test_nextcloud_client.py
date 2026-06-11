"""Tests for the Nextcloud client (all HTTP calls mocked)."""

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

import server.nextcloud_client as nc


@pytest.fixture(autouse=True)
def nextcloud_config(monkeypatch):
    """Provide fake credentials and reset the per-process base-folder cache."""
    monkeypatch.setattr(nc, "NEXTCLOUD_URL", "https://cloud.example")
    monkeypatch.setattr(nc, "NEXTCLOUD_USERNAME", "fotobox")
    monkeypatch.setattr(nc, "NEXTCLOUD_PASSWORD", "app-password")
    monkeypatch.setattr(nc, "NEXTCLOUD_BASE_FOLDER", "Fotobox")
    nc._base_folder_ready = False
    yield
    nc._base_folder_ready = False


def _response(status_code=200, json_data=None):
    res = MagicMock()
    res.status_code = status_code
    res.json.return_value = json_data or {}
    return res


class TestWebdavUrl:
    def test_basic_url(self):
        url = nc._get_webdav_url("Fotobox/abc")
        assert url == "https://cloud.example/remote.php/dav/files/fotobox/Fotobox/abc"

    def test_special_characters_quoted(self):
        url = nc._get_webdav_url("Fotobox/foto mit leerzeichen.jpg")
        assert "%20" in url


class TestEnsureBaseFolder:
    def test_creates_folder_when_missing(self):
        with patch.object(nc.requests, "request") as mock_req:
            mock_req.side_effect = [_response(404), _response(201)]
            assert nc.ensure_base_folder() is True

        methods = [c.args[0] for c in mock_req.call_args_list]
        assert methods == ["PROPFIND", "MKCOL"]

    def test_existing_folder(self):
        with patch.object(nc.requests, "request", return_value=_response(207)):
            assert nc.ensure_base_folder() is True

    def test_result_is_cached_per_process(self):
        with patch.object(nc.requests, "request", return_value=_response(207)) as mock_req:
            nc.ensure_base_folder()
            nc.ensure_base_folder()
        assert mock_req.call_count == 1

    def test_unreachable_returns_false(self):
        with patch.object(nc.requests, "request",
                          side_effect=requests.ConnectionError("down")):
            assert nc.ensure_base_folder() is False

    def test_all_requests_have_timeout(self):
        with patch.object(nc.requests, "request", return_value=_response(207)) as mock_req:
            nc.ensure_base_folder()
        assert mock_req.call_args.kwargs.get("timeout")


class TestCreateSharedFolder:
    def test_success(self):
        share_json = {"ocs": {"data": {"url": "https://cloud.example/s/xyz"}}}
        with patch.object(nc.requests, "request", return_value=_response(201)), \
             patch.object(nc.requests, "post", return_value=_response(200, share_json)):
            url = nc.create_shared_folder("abc123")
        assert url == "https://cloud.example/s/xyz"

    def test_mkcol_failure_returns_empty(self):
        with patch.object(nc.requests, "request", return_value=_response(500)):
            assert nc.create_shared_folder("abc123") == ""

    def test_share_api_failure_returns_empty(self):
        with patch.object(nc.requests, "request", return_value=_response(201)), \
             patch.object(nc.requests, "post", return_value=_response(403)):
            assert nc.create_shared_folder("abc123") == ""

    def test_network_error_returns_empty(self):
        with patch.object(nc.requests, "request",
                          side_effect=requests.ConnectionError("down")):
            assert nc.create_shared_folder("abc123") == ""


class TestProcessNextcloudUpload:
    def test_missing_credentials_returns_empty(self, monkeypatch):
        monkeypatch.setattr(nc, "NEXTCLOUD_URL", "")
        assert nc.process_nextcloud_upload(["a.jpg"]) == ""

    def test_success_starts_background_upload(self):
        with patch.object(nc, "ensure_base_folder", return_value=True), \
             patch.object(nc, "create_shared_folder",
                          return_value="https://cloud.example/s/xyz"), \
             patch.object(nc.threading, "Thread") as mock_thread:
            url = nc.process_nextcloud_upload(["a.jpg", "b.jpg"])

        assert url == "https://cloud.example/s/xyz"
        mock_thread.assert_called_once()
        assert mock_thread.call_args.kwargs["daemon"] is True

    def test_unreachable_cloud_returns_empty_without_upload(self):
        with patch.object(nc, "ensure_base_folder", return_value=False), \
             patch.object(nc.threading, "Thread") as mock_thread:
            assert nc.process_nextcloud_upload(["a.jpg"]) == ""
        mock_thread.assert_not_called()

    def test_share_failure_returns_empty(self):
        with patch.object(nc, "ensure_base_folder", return_value=True), \
             patch.object(nc, "create_shared_folder", return_value=""), \
             patch.object(nc.threading, "Thread") as mock_thread:
            assert nc.process_nextcloud_upload(["a.jpg"]) == ""
        mock_thread.assert_not_called()

    def test_session_ids_are_unique(self):
        seen = set()
        with patch.object(nc, "ensure_base_folder", return_value=True), \
             patch.object(nc, "create_shared_folder",
                          side_effect=lambda sid: seen.add(sid) or "https://x/s/1"), \
             patch.object(nc.threading, "Thread"):
            for _ in range(10):
                nc.process_nextcloud_upload(["a.jpg"])
        assert len(seen) == 10


class TestUploadWorker:
    def test_uploads_each_photo(self, tmp_path, monkeypatch):
        photo_dir = str(tmp_path)
        monkeypatch.setattr(nc, "PHOTO_DIR", photo_dir)
        for name in ("a.jpg", "b.jpg"):
            with open(os.path.join(photo_dir, name), "wb") as f:
                f.write(b"\xff\xd8data")

        with patch.object(nc.requests, "put", return_value=_response(201)) as mock_put:
            nc._upload_worker("sess01", ["a.jpg", "b.jpg"])

        assert mock_put.call_count == 2
        assert all(c.kwargs.get("timeout") for c in mock_put.call_args_list)

    def test_missing_file_does_not_abort_batch(self, tmp_path, monkeypatch):
        photo_dir = str(tmp_path)
        monkeypatch.setattr(nc, "PHOTO_DIR", photo_dir)
        with open(os.path.join(photo_dir, "b.jpg"), "wb") as f:
            f.write(b"\xff\xd8data")

        with patch.object(nc.requests, "put", return_value=_response(201)) as mock_put:
            nc._upload_worker("sess01", ["missing.jpg", "b.jpg"])

        # missing.jpg schlägt fehl, b.jpg wird trotzdem hochgeladen
        assert mock_put.call_count == 1
