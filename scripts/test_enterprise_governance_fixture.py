"""Exercise enterprise governance routes against an isolated temporary database."""

import os
import sys
import tempfile
from pathlib import Path


database_file = Path(tempfile.gettempdir()) / "ba-enterprise-governance-fixture.sqlite3"
database_file.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{database_file}"
os.environ["AUTH_MODE"] = "hybrid"
os.environ["JWT_SECRET"] = "fixture-only-signing-key-with-at-least-32-bytes"
os.environ["LOCAL_ROOT_PASSWORD"] = "FixtureRoot!Pass2026"
os.environ["ANALYSIS_REQUIRE_REDIS"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AnalysisArtifact
from app.routes.analyze import reusable_entity_matches


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def expect(response, status: int, context: str):
    assert response.status_code == status, f"{context}: {response.status_code} {response.text}"
    return response.json() if response.content else None


def create_project(name: str, owner_user_id: str) -> int:
    db = SessionLocal()
    try:
        project = AnalysisArtifact(
            project_name=name,
            project_type="internal",
            transcript="Fixture source",
            analysis_json={"semantic_model": {}},
            tenant_id="local",
            owner_user_id=owner_user_id,
            is_archived=False,
            is_deleted=False,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project.id
    finally:
        db.close()


def run_fixture() -> None:
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as client:
        root_login = expect(
            client.post(
                "/auth/token",
                json={"email": "root@ba-optimization.local", "password": "FixtureRoot!Pass2026"},
            ),
            200,
            "root login",
        )
        root_headers = auth_header(root_login["access_token"])
        organization = expect(
            client.post(
                "/settings/tenants",
                headers=root_headers,
                json={"id": "fixture-organization", "name": "Fixture Organization"},
            ),
            200,
            "create tenant organization",
        )
        assert organization["id"] == "fixture-organization"
        tenants = expect(client.get("/settings/tenants", headers=root_headers), 200, "list tenant organizations")
        assert {tenant["id"] for tenant in tenants} == {"local", "fixture-organization"}

        alpha = expect(client.post("/teams", headers=root_headers, json={"name": "Alpha Delivery"}), 200, "create alpha")
        beta = expect(client.post("/teams", headers=root_headers, json={"name": "Beta Controls"}), 200, "create beta")
        viewer = expect(
            client.post(
                "/settings/users",
                headers=root_headers,
                json={
                    "name": "Fixture Viewer",
                    "username": "fixture.viewer",
                    "email": "fixture.viewer@example.test",
                    "role": "viewer",
                    "password": "FixtureViewer!Pass2026",
                    "auth_source": "local",
                },
            ),
            200,
            "create viewer",
        )
        expect(
            client.put(
                f"/teams/{alpha['id']}/members",
                headers=root_headers,
                json={"user_ids": [viewer["id"]]},
            ),
            200,
            "add viewer to alpha",
        )

        assigned_project_id = create_project("Assigned Fixture Project", root_login["user"]["id"])
        hidden_project_id = create_project("Hidden Fixture Project", root_login["user"]["id"])
        mapping = expect(client.get("/settings/project-team-mapping", headers=root_headers), 200, "mapping list")
        assert {item["id"] for item in mapping["projects"]} == {assigned_project_id, hidden_project_id}

        expect(
            client.put(
                f"/settings/projects/{assigned_project_id}/teams",
                headers=root_headers,
                json={"team_ids": [alpha["id"], beta["id"]]},
            ),
            200,
            "assign collaborating teams",
        )

        viewer_login = expect(
            client.post(
                "/auth/token",
                json={"email": viewer["email"], "password": "FixtureViewer!Pass2026"},
            ),
            200,
            "viewer login",
        )
        viewer_headers = auth_header(viewer_login["access_token"])
        visible = expect(client.get("/analysis-artifacts", headers=viewer_headers), 200, "team visibility")
        assert [project["id"] for project in visible] == [assigned_project_id]
        assert {team["id"] for team in visible[0]["teams"]} == {alpha["id"], beta["id"]}
        expect(
            client.post(
                "/auth/change-password",
                headers=viewer_headers,
                json={"current_password": "FixtureViewer!Pass2026", "new_password": "FixtureViewer!Changed2026"},
            ),
            200,
            "profile password change",
        )
        expect(
            client.post(
                "/auth/token",
                json={"email": viewer["email"], "password": "FixtureViewer!Changed2026"},
            ),
            200,
            "login with changed password",
        )

        expect(
            client.put(
                f"/settings/projects/{hidden_project_id}/teams",
                headers=root_headers,
                json={"team_ids": [alpha["id"]]},
            ),
            409,
            "team single-project policy",
        )
        expect(client.put(f"/teams/{alpha['id']}", headers=root_headers, json={"allow_multiple_projects": True}), 200, "enable team multi-project work")
        expect(client.put(f"/settings/projects/{hidden_project_id}/teams", headers=root_headers, json={"team_ids": [alpha["id"]]}), 200, "assign team to second project")

        impact = expect(
            client.get(f"/settings/archive-impact/project/{assigned_project_id}", headers=root_headers),
            200,
            "project archive impact",
        )
        assert impact["orphan_risk"] is False and any("assigned team" in item for item in impact["dependencies"])
        expect(
            client.post(f"/settings/archive/projects/{assigned_project_id}", headers=root_headers),
            200,
            "archive project",
        )
        archived = expect(client.get("/settings/archive", headers=root_headers), 200, "archive fixture list")
        assert [project["id"] for project in archived["projects"]] == [assigned_project_id]
        after_archive = expect(client.get("/analysis-artifacts", headers=viewer_headers), 200, "archived visibility")
        assert [project["id"] for project in after_archive] == [hidden_project_id]
        expect(
            client.post(f"/settings/archive/projects/{assigned_project_id}/restore", headers=root_headers),
            200,
            "restore project",
        )
        restored = expect(client.get("/analysis-artifacts", headers=viewer_headers), 200, "restored visibility")
        assert {project["id"] for project in restored} == {assigned_project_id, hidden_project_id}

        expect(client.post(f"/teams/{beta['id']}/archive", headers=root_headers), 200, "archive team")
        archived = expect(client.get("/settings/archive", headers=root_headers), 200, "archived team list")
        assert [team["id"] for team in archived["teams"]] == [beta["id"]]
        expect(client.post(f"/teams/{beta['id']}/restore", headers=root_headers), 200, "restore team")

        matches = reusable_entity_matches(
            {"FR1": {"id": "FR1", "type": "requirement", "name": "Daily SAP actuals synchronization", "description": "Synchronize SAP actuals daily"}},
            {"REQ9": {"id": "REQ9", "type": "requirement", "name": "SAP actuals daily sync", "description": "Daily synchronization of SAP actuals"}},
        )
        assert matches and matches[0]["existing_id"] == "REQ9"
        assert not reusable_entity_matches(
            {"FR1": {"id": "FR1", "type": "requirement", "name": "Daily SAP actuals synchronization", "description": "Synchronize SAP actuals daily"}},
            {"RISK1": {"id": "RISK1", "type": "risk", "name": "Office lease renewal", "description": "Renew building lease"}},
        )

    print("PASS enterprise governance fixture: JWT, mapping, access, archive, and restore")


if __name__ == "__main__":
    try:
        run_fixture()
    finally:
        engine.dispose()
        database_file.unlink(missing_ok=True)
