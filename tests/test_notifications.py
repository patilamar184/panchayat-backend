def _setup(client, make_citizen, make_employee, make_complaint, admin_headers):
    _, citizen = make_citizen()
    emp, employee = make_employee()
    cid = make_complaint(citizen)["id"]
    client.post(f"/api/v1/admin/complaints/{cid}/assign", json={"employee_id": emp["id"]}, headers=admin_headers)
    client.post(f"/api/v1/employee/complaints/{cid}/status", json={"status": "in_progress"}, headers=employee)
    return citizen, employee


def test_unread_listing_count_and_mark_read(client, make_citizen, make_employee, make_complaint, admin_headers):
    citizen, _ = _setup(client, make_citizen, make_employee, make_complaint, admin_headers)
    count = client.get("/api/v1/notifications/unread-count", headers=citizen).json()["unread"]
    assert count == 2  # assigned + in progress
    unread = client.get("/api/v1/notifications/unread", headers=citizen).json()
    assert unread["total"] == 2
    first = unread["items"][0]["id"]
    r = client.post(f"/api/v1/notifications/{first}/read", headers=citizen)
    assert r.status_code == 200 and r.json()["is_read"] is True
    assert client.get("/api/v1/notifications/unread-count", headers=citizen).json()["unread"] == 1
    assert client.get("/api/v1/notifications?unread_only=true", headers=citizen).json()["total"] == 1


def test_mark_all_read(client, make_citizen, make_employee, make_complaint, admin_headers):
    citizen, _ = _setup(client, make_citizen, make_employee, make_complaint, admin_headers)
    assert client.post("/api/v1/notifications/read-all", headers=citizen).json() == {"unread": 0}
    assert client.get("/api/v1/notifications/unread", headers=citizen).json()["total"] == 0
    assert client.get("/api/v1/notifications", headers=citizen).json()["total"] == 2


def test_notifications_are_private(client, make_citizen, make_employee, make_complaint, admin_headers):
    citizen, employee = _setup(client, make_citizen, make_employee, make_complaint, admin_headers)
    nid = client.get("/api/v1/notifications", headers=citizen).json()["items"][0]["id"]
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=employee).status_code == 404
    ids = {n["id"] for n in client.get("/api/v1/notifications", headers=employee).json()["items"]}
    assert nid not in ids
    # employee's "read-all" must not touch the citizen's notifications
    client.post("/api/v1/notifications/read-all", headers=employee)
    assert client.get("/api/v1/notifications/unread-count", headers=citizen).json()["unread"] == 2
