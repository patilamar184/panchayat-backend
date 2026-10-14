def test_employee_starts_pending_and_is_blocked(client, make_employee):
    user, headers = make_employee(approve=False)
    assert user["approval_status"] == "pending"
    r = client.get("/api/v1/employee/complaints", headers=headers)
    assert r.status_code == 403


def test_admin_approves_employee_and_notifies(client, make_employee, admin_headers):
    user, headers = make_employee(approve=False)
    pending = client.get("/api/v1/admin/employees?approval_status=pending", headers=admin_headers)
    assert [u["id"] for u in pending.json()["items"]] == [user["id"]]
    assert client.post(f"/api/v1/admin/employees/{user['id']}/approve", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/employee/complaints", headers=headers).status_code == 200
    notes = client.get("/api/v1/notifications", headers=headers).json()["items"]
    assert notes[0]["type"] == "employee_approved"
    again = client.post(f"/api/v1/admin/employees/{user['id']}/approve", headers=admin_headers)
    assert again.status_code == 409


def test_admin_rejects_employee(client, make_employee, admin_headers):
    user, headers = make_employee(approve=False)
    r = client.post(
        f"/api/v1/admin/employees/{user['id']}/reject", json={"reason": "No ID"}, headers=admin_headers
    )
    assert r.status_code == 200 and r.json()["approval_status"] == "rejected"
    assert client.get("/api/v1/employee/complaints", headers=headers).status_code == 403
    note = client.get("/api/v1/notifications", headers=headers).json()["items"][0]
    assert note["type"] == "employee_rejected" and "No ID" in note["message"]


def test_role_boundaries(client, make_citizen, make_employee, admin_headers):
    _, citizen = make_citizen()
    _, employee = make_employee()
    for headers in (citizen, employee):
        assert client.get("/api/v1/admin/complaints", headers=headers).status_code == 403
        assert client.get("/api/v1/admin/employees", headers=headers).status_code == 403
    assert client.get("/api/v1/employee/complaints", headers=citizen).status_code == 403
    assert client.post("/api/v1/complaints", json={}, headers=employee).status_code == 403
    assert client.get("/api/v1/employee/complaints", headers=admin_headers).status_code == 403


def test_cannot_assign_to_unapproved_or_non_employee(
    client, make_citizen, make_employee, make_complaint, admin_headers
):
    citizen, ch = make_citizen()
    pending, _ = make_employee("pending@example.com", approve=False)
    complaint = make_complaint(ch)
    for target in (pending["id"], citizen["id"], 9999):
        r = client.post(
            f"/api/v1/admin/complaints/{complaint['id']}/assign",
            json={"employee_id": target},
            headers=admin_headers,
        )
        assert r.status_code == 400
