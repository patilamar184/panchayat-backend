def test_citizen_creates_and_lists_only_own(client, make_citizen, make_complaint):
    _, a = make_citizen("a@example.com")
    _, b = make_citizen("b@example.com")
    ca = make_complaint(a)
    make_complaint(b, title="Water leak on 5th street")
    assert ca["status"] == "reported" and ca["assigned_employee_id"] is None
    mine = client.get("/api/v1/complaints", headers=a).json()
    assert mine["total"] == 1 and mine["items"][0]["id"] == ca["id"]


def test_ownership_enforced_with_404(client, make_citizen, make_complaint):
    _, a = make_citizen("a@example.com")
    _, b = make_citizen("b@example.com")
    c = make_complaint(a)
    assert client.get(f"/api/v1/complaints/{c['id']}", headers=b).status_code == 404
    assert client.get(f"/api/v1/complaints/{c['id']}/history", headers=b).status_code == 404
    assert client.get(f"/api/v1/complaints/{c['id']}", headers=a).status_code == 200


def test_validation(client, make_citizen):
    _, h = make_citizen()
    base = {
        "title": "Bad one",
        "description": "Long enough description here.",
        "category": "roads",
        "latitude": 10,
        "longitude": 10,
        "address": "Somewhere",
    }
    assert client.post("/api/v1/complaints", json={**base, "latitude": 91}, headers=h).status_code == 422
    assert client.post("/api/v1/complaints", json={**base, "longitude": -181}, headers=h).status_code == 422
    assert client.post("/api/v1/complaints", json={**base, "category": "parks"}, headers=h).status_code == 422


def test_admin_filter_and_pagination(client, make_citizen, make_complaint, admin_headers):
    _, h = make_citizen()
    make_complaint(h, category="roads", title="Road crack near school")
    make_complaint(h, category="water", title="Water pipe burst")
    make_complaint(h, category="water", title="Water supply stopped")
    r = client.get("/api/v1/admin/complaints?category=water", headers=admin_headers).json()
    assert r["total"] == 2
    r = client.get("/api/v1/admin/complaints?page=1&page_size=2", headers=admin_headers).json()
    assert len(r["items"]) == 2 and r["total"] == 3
    r = client.get("/api/v1/admin/complaints?q=pipe", headers=admin_headers).json()
    assert r["total"] == 1
    r = client.get("/api/v1/admin/complaints?unassigned=true&status=reported", headers=admin_headers).json()
    assert r["total"] == 3


def test_full_workflow_history_and_notifications(
    client, make_citizen, make_employee, make_complaint, admin_headers
):
    _, citizen = make_citizen()
    emp, employee = make_employee()
    cid = make_complaint(citizen)["id"]

    r = client.post(f"/api/v1/admin/complaints/{cid}/status", json={"status": "under_review"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "under_review"

    r = client.post(
        f"/api/v1/admin/complaints/{cid}/assign",
        json={"employee_id": emp["id"], "notes": "Please inspect"},
        headers=admin_headers,
    )
    assert r.status_code == 200 and r.json()["status"] == "assigned"

    queue = client.get("/api/v1/employee/complaints", headers=employee).json()
    assert [c["id"] for c in queue["items"]] == [cid]

    r = client.post(f"/api/v1/employee/complaints/{cid}/status", json={"status": "in_progress"}, headers=employee)
    assert r.status_code == 200

    no_notes = client.post(f"/api/v1/employee/complaints/{cid}/status", json={"status": "resolved"}, headers=employee)
    assert no_notes.status_code == 422
    r = client.post(
        f"/api/v1/employee/complaints/{cid}/status",
        json={"status": "resolved", "notes": "Filled the pothole"},
        headers=employee,
    )
    assert r.status_code == 200 and r.json()["resolution_notes"] == "Filled the pothole"
    assert r.json()["resolved_at"] is not None

    r = client.post(f"/api/v1/admin/complaints/{cid}/status", json={"status": "closed"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["closed_at"] is not None

    history = client.get(f"/api/v1/complaints/{cid}/history", headers=citizen).json()
    assert [(h["action"], h["previous_status"], h["new_status"]) for h in history] == [
        ("created", None, "reported"),
        ("status_changed", "reported", "under_review"),
        ("assigned", "under_review", "assigned"),
        ("status_changed", "assigned", "in_progress"),
        ("resolved", "in_progress", "resolved"),
        ("closed", "resolved", "closed"),
    ]
    assert all(h["actor_id"] is not None for h in history)

    notes = client.get("/api/v1/notifications", headers=citizen).json()["items"]
    types = {n["type"] for n in notes}
    assert {"complaint_assigned", "status_changed", "complaint_resolved", "complaint_closed"} <= types
    emp_notes = client.get("/api/v1/notifications", headers=employee).json()["items"]
    assert any(n["type"] == "complaint_assigned" and n["complaint_id"] == cid for n in emp_notes)


def test_invalid_transitions_rejected(client, make_citizen, make_employee, make_complaint, admin_headers):
    _, citizen = make_citizen()
    emp, employee = make_employee()
    cid = make_complaint(citizen)["id"]
    # citizens cannot change status; admin cannot skip steps; closing unresolved needs notes
    assert client.post(f"/api/v1/admin/complaints/{cid}/status", json={"status": "resolved"}, headers=admin_headers).status_code == 409
    assert client.post(f"/api/v1/admin/complaints/{cid}/status", json={"status": "reported"}, headers=admin_headers).status_code == 409
    client.post(f"/api/v1/admin/complaints/{cid}/status", json={"status": "under_review"}, headers=admin_headers)
    assert client.post(f"/api/v1/admin/complaints/{cid}/status", json={"status": "closed"}, headers=admin_headers).status_code == 422
    closed = client.post(
        f"/api/v1/admin/complaints/{cid}/status",
        json={"status": "closed", "notes": "Duplicate report"},
        headers=admin_headers,
    )
    assert closed.status_code == 200
    # closed is final
    assert client.post(f"/api/v1/admin/complaints/{cid}/status", json={"status": "under_review"}, headers=admin_headers).status_code == 409
    assert (
        client.post(f"/api/v1/admin/complaints/{cid}/assign", json={"employee_id": emp["id"]}, headers=admin_headers).status_code == 409
    )


def test_employee_only_sees_and_updates_assigned(
    client, make_citizen, make_employee, make_complaint, admin_headers
):
    _, citizen = make_citizen()
    emp1, e1 = make_employee("e1@example.com")
    _, e2 = make_employee("e2@example.com")
    cid = make_complaint(citizen)["id"]
    client.post(f"/api/v1/admin/complaints/{cid}/assign", json={"employee_id": emp1["id"]}, headers=admin_headers)

    assert client.get("/api/v1/employee/complaints", headers=e2).json()["total"] == 0
    assert client.get(f"/api/v1/complaints/{cid}", headers=e2).status_code == 404
    r = client.post(f"/api/v1/employee/complaints/{cid}/status", json={"status": "in_progress"}, headers=e2)
    assert r.status_code == 404
    assert client.get(f"/api/v1/complaints/{cid}", headers=e1).status_code == 200
    # employees cannot do admin transitions on their own complaint
    r = client.post(f"/api/v1/employee/complaints/{cid}/status", json={"status": "closed"}, headers=e1)
    assert r.status_code == 409


def test_reassignment_is_recorded(client, make_citizen, make_employee, make_complaint, admin_headers):
    _, citizen = make_citizen()
    e1, _ = make_employee("e1@example.com")
    e2, _ = make_employee("e2@example.com")
    cid = make_complaint(citizen)["id"]
    for e in (e1, e2):
        r = client.post(f"/api/v1/admin/complaints/{cid}/assign", json={"employee_id": e["id"]}, headers=admin_headers)
        assert r.status_code == 200
    assert r.json()["assigned_employee_id"] == e2["id"]
    actions = [h["action"] for h in client.get(f"/api/v1/complaints/{cid}/history", headers=admin_headers).json()]
    assert actions == ["created", "assigned", "reassigned"]
