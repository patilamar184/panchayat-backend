import os
import tempfile

# Settings must exist before the app is imported.
os.environ["DATABASE_URL"] = "sqlite+pysqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-characters-long"
os.environ["MEDIA_ROOT"] = tempfile.mkdtemp(prefix="panchayat-test-media-")
os.environ["MAX_UPLOAD_BYTES"] = str(200 * 1024)

import io  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import UserRole  # noqa: E402
from app.services import users as user_svc  # noqa: E402

PASSWORD = "correct-horse-1"


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture()
def db(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture()
def client(session_factory):
    def override():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(client, email, password=PASSWORD) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def make_citizen(client):
    def _make(email="citizen@example.com"):
        r = client.post(
            "/api/v1/auth/register/citizen",
            json={"email": email, "password": PASSWORD, "full_name": "Test Citizen"},
        )
        assert r.status_code == 201, r.text
        return r.json(), _login(client, email)

    return _make


@pytest.fixture()
def admin_headers(client, db):
    user_svc.create_user(
        db, email="admin@example.com", password=PASSWORD, full_name="Admin", role=UserRole.admin
    )
    return _login(client, "admin@example.com")


@pytest.fixture()
def make_employee(client, admin_headers):
    def _make(email="worker@example.com", approve=True):
        r = client.post(
            "/api/v1/auth/register/employee",
            json={
                "email": email,
                "password": PASSWORD,
                "full_name": "Test Worker",
                "department": "Public Works",
            },
        )
        assert r.status_code == 201, r.text
        user = r.json()
        if approve:
            a = client.post(f"/api/v1/admin/employees/{user['id']}/approve", headers=admin_headers)
            assert a.status_code == 200, a.text
        return user, _login(client, email)

    return _make


COMPLAINT = {
    "title": "Pothole on Main Road",
    "description": "A deep pothole near the bus stop is dangerous for bikes.",
    "category": "roads",
    "latitude": 18.52,
    "longitude": 73.85,
    "address": "Main Road, Pune",
    "is_public": True,
}


@pytest.fixture()
def make_complaint(client):
    def _make(headers, **overrides):
        r = client.post("/api/v1/complaints", json={**COMPLAINT, **overrides}, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()

    return _make


def image_bytes(fmt="PNG", size=(32, 24)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buf, format=fmt)
    return buf.getvalue()
