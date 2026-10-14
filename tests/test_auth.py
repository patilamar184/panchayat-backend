from tests.conftest import PASSWORD


def test_register_and_login_citizen(client, make_citizen):
    user, headers = make_citizen()
    assert user["role"] == "citizen" and user["approval_status"] == "approved"
    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200 and me.json()["email"] == "citizen@example.com"


def test_duplicate_email_is_case_insensitive(client, make_citizen):
    make_citizen("Dup@Example.com")
    r = client.post(
        "/api/v1/auth/register/citizen",
        json={"email": "dup@example.com", "password": PASSWORD, "full_name": "Other Person"},
    )
    assert r.status_code == 409


def test_cannot_register_as_admin(client):
    r = client.post(
        "/api/v1/auth/register/citizen",
        json={"email": "x@example.com", "password": PASSWORD, "full_name": "Sneaky", "role": "admin"},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "citizen"


def test_wrong_password_and_unknown_user(client, make_citizen):
    make_citizen()
    bad = client.post("/api/v1/auth/login", json={"email": "citizen@example.com", "password": "nope-nope-1"})
    unknown = client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-1"})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json()


def test_weak_password_rejected(client):
    r = client.post(
        "/api/v1/auth/register/citizen",
        json={"email": "w@example.com", "password": "short", "full_name": "Weak Pass"},
    )
    assert r.status_code == 422


def test_protected_routes_need_valid_token(client):
    assert client.get("/api/v1/users/me").status_code == 401
    r = client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_oauth_token_endpoint_for_swagger(client, make_citizen):
    make_citizen()
    r = client.post("/api/v1/auth/token", data={"username": "citizen@example.com", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"


def test_profile_update_and_password_change(client, make_citizen):
    _, headers = make_citizen()
    r = client.patch("/api/v1/users/me", json={"full_name": "New Name"}, headers=headers)
    assert r.json()["full_name"] == "New Name"
    wrong = client.post(
        "/api/v1/users/me/password",
        json={"current_password": "wrong-pass-1", "new_password": "brand-new-pass-2"},
        headers=headers,
    )
    assert wrong.status_code == 400
    ok = client.post(
        "/api/v1/users/me/password",
        json={"current_password": PASSWORD, "new_password": "brand-new-pass-2"},
        headers=headers,
    )
    assert ok.status_code == 200
    relog = client.post(
        "/api/v1/auth/login", json={"email": "citizen@example.com", "password": "brand-new-pass-2"}
    )
    assert relog.status_code == 200


def test_deactivated_account_is_locked_out(client, make_citizen):
    _, headers = make_citizen()
    bad = client.post("/api/v1/users/me/deactivate", json={"password": "wrong-pass-1"}, headers=headers)
    assert bad.status_code == 400
    ok = client.post("/api/v1/users/me/deactivate", json={"password": PASSWORD}, headers=headers)
    assert ok.status_code == 200
    assert client.get("/api/v1/users/me", headers=headers).status_code == 403
    login = client.post("/api/v1/auth/login", json={"email": "citizen@example.com", "password": PASSWORD})
    assert login.status_code == 403
