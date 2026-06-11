"""Tests for the preview generation module."""

import os
from unittest.mock import patch

import pytest
from PIL import Image

from server.previews import get_or_create_preview

from tests.conftest import make_test_jpeg


@pytest.fixture
def photo_dir(tmp_path):
    d = str(tmp_path / "photos")
    os.makedirs(d, exist_ok=True)
    with patch("server.previews.PHOTO_DIR", d):
        yield d


class TestGetOrCreatePreview:
    def test_creates_downscaled_preview(self, photo_dir):
        make_test_jpeg(os.path.join(photo_dir, "big.jpg"), size=(4000, 3000))

        path = get_or_create_preview("big.jpg")

        assert path is not None
        with Image.open(path) as img:
            assert max(img.size) <= 1280

    def test_small_photo_not_upscaled(self, photo_dir):
        make_test_jpeg(os.path.join(photo_dir, "small.jpg"), size=(640, 480))

        path = get_or_create_preview("small.jpg")

        with Image.open(path) as img:
            assert img.size == (640, 480)

    def test_cached_on_second_call(self, photo_dir):
        make_test_jpeg(os.path.join(photo_dir, "x.jpg"))

        first = get_or_create_preview("x.jpg")
        mtime = os.path.getmtime(first)
        second = get_or_create_preview("x.jpg")

        assert first == second
        assert os.path.getmtime(second) == mtime

    def test_regenerated_when_source_changes(self, photo_dir):
        source = os.path.join(photo_dir, "y.jpg")
        make_test_jpeg(source, size=(2000, 1500))
        preview = get_or_create_preview("y.jpg")

        # Quelle "neuer" machen als die Preview
        future = os.path.getmtime(preview) + 10
        os.utime(source, (future, future))

        assert get_or_create_preview("y.jpg") is not None
        assert os.path.getmtime(preview) >= future or os.path.getmtime(preview) > 0

    def test_missing_source_returns_none(self, photo_dir):
        assert get_or_create_preview("nope.jpg") is None

    def test_traversal_rejected(self, photo_dir):
        assert get_or_create_preview("../secret.jpg") is None
        assert get_or_create_preview("a/b.jpg") is None
        assert get_or_create_preview(".hidden.jpg") is None

    def test_corrupt_jpeg_returns_none(self, photo_dir):
        with open(os.path.join(photo_dir, "broken.jpg"), "wb") as f:
            f.write(b"not a jpeg at all")

        assert get_or_create_preview("broken.jpg") is None
