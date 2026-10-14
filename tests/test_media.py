import io
import os
from pathlib import Path

from PIL import Image

from app.core.config import get_settings
from tests.conftest import image_bytes


def _upload(client, headers, cid, data, name="photo.png", ctype="image/png"):
    return client.post(
        f"/api/v1/complaints/{cid}/media", files={"file": (name, data, ctype)}, headers=headers
    )


def test_upload_list_download_delete(client, make_citizen, make_complaint):
    _, h = make_citizen()
    cid = make_complaint(h)["id"]
    r = _upload(client, h, cid, image_bytes("PNG"))
    assert r.status_code == 201, r.text
    media = r.json()
    assert media["width"] == 32 and media["height"] == 24 and media["content_type"] == "image/png"
    assert "stored_filename" not in media

    assert [m["id"] for m in client.get(f"/api/v1/complaints/{cid}/media", headers=h).json()] == [media["id"]]
    file = client.get(f"/api/v1/media/{media['id']}/file", headers=h)
    assert file.status_code == 200 and file.headers["content-type"] == "image/png"
    assert file.content == image_bytes("PNG")

    stored = list(Path(get_settings().media_root, "complaints", str(cid)).iterdir())
    assert len(stored) == 1
    assert client.delete(f"/api/v1/media/{media['id']}", headers=h).status_code == 204
    assert not stored[0].exists()
    assert client.get(f"/api/v1/media/{media['id']}/file", headers=h).status_code == 404


def test_accepts_jpeg_and_webp(client, make_citizen, make_complaint):
    _, h = make_citizen()
    cid = make_complaint(h)["id"]
    assert _upload(client, h, cid, image_bytes("JPEG"), "a.jpg", "image/jpeg").status_code == 201
    assert _upload(client, h, cid, image_bytes("WEBP"), "b.webp", "image/webp").status_code == 201


def test_rejects_bad_extension_type_and_content(client, make_citizen, make_complaint):
    _, h = make_citizen()
    cid = make_complaint(h)["id"]
    png = image_bytes("PNG")
    assert _upload(client, h, cid, png, "a.gif", "image/gif").status_code == 415
    assert _upload(client, h, cid, png, "a.png", "image/jpeg").status_code == 415  # declared type mismatch
    assert _upload(client, h, cid, png, "a.jpg", "image/jpeg").status_code == 415  # decoded format mismatch
    assert _upload(client, h, cid, b"<?php echo 1; ?>", "a.png", "image/png").status_code == 400
    assert _upload(client, h, cid, b"", "a.png", "image/png").status_code == 400
    assert _upload(client, h, cid, png, "a.svg", "image/svg+xml").status_code == 415


def test_rejects_oversized_file(client, make_citizen, make_complaint):
    _, h = make_citizen()
    cid = make_complaint(h)["id"]
    buf = io.BytesIO()
    Image.frombytes("RGB", (400, 400), os.urandom(400 * 400 * 3)).save(buf, format="PNG")
    assert len(buf.getvalue()) > 200 * 1024
    assert _upload(client, h, cid, buf.getvalue()).status_code == 413


def test_media_limited_to_owner(client, make_citizen, make_complaint, admin_headers):
    _, owner = make_citizen("owner@example.com")
    _, other = make_citizen("other@example.com")
    cid = make_complaint(owner)["id"]
    mid = _upload(client, owner, cid, image_bytes()).json()["id"]
    assert _upload(client, other, cid, image_bytes()).status_code == 404
    assert client.get(f"/api/v1/complaints/{cid}/media", headers=other).status_code == 404
    assert client.get(f"/api/v1/media/{mid}/file", headers=other).status_code == 404
    assert client.delete(f"/api/v1/media/{mid}", headers=other).status_code == 404
    assert client.get(f"/api/v1/media/{mid}/file", headers=admin_headers).status_code == 403
    assert client.get(f"/api/v1/media/{mid}/file").status_code == 401
    assert client.get(f"/api/v1/media/{mid}/file", headers=owner).status_code == 200


def test_filename_is_not_used_for_storage_path(client, make_citizen, make_complaint):
    _, h = make_citizen()
    cid = make_complaint(h)["id"]
    r = _upload(client, h, cid, image_bytes(), "../../evil.png")
    assert r.status_code == 201
    assert r.json()["original_filename"] == "evil.png"
