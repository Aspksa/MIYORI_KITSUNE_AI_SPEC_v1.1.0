from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from miyori.config import settings
from miyori.db import (
    connect,
    create_home_device,
    create_parental_profile,
    create_project,
    init_db,
    list_audit_events,
)
from miyori.nexus_home import (
    HOME_HEARTBEAT_TTL_SECONDS,
    NEXUS_HOME_SCHEMA_VERSION,
    bind_parental_profile,
    build_nexus_home,
    init_nexus_home_db,
    link_home_device,
    record_home_heartbeat,
    unlink_home_device,
)


class NexusHomeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        init_nexus_home_db()
        self.project = create_project("NEXUS Home", kind="home")
        self.project_id = int(self.project["id"])
        self.device = create_home_device(
            self.project_id,
            name="Tablet",
            device_type="tablet",
            address="living-room",
            status="online",
            notes="legacy status must not define connectivity",
        )
        self.device_id = int(self.device["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_legacy_status_never_counts_as_runtime_connectivity(self) -> None:
        page = build_nexus_home(self.project_id)
        self.assertEqual(page["schema_version"], NEXUS_HOME_SCHEMA_VERSION)
        item = page["devices"][0]
        self.assertEqual(item["declared_status"], "online")
        self.assertEqual(item["connectivity"]["state"], "unlinked")
        self.assertFalse(item["connectivity"]["online"])
        self.assertEqual(page["counts"]["online"], 0)
        self.assertFalse(page["policy"]["legacy_status_is_connectivity_source"])
        self.assertFalse(page["policy"]["network_scanning_enabled"])

    def test_link_returns_credential_once_and_stores_only_hash(self) -> None:
        result = link_home_device(
            self.project_id,
            self.device_id,
            capabilities=["presence", "parental_policy"],
        )
        credential = result["credential"]
        self.assertTrue(result["credential_exposed_once"])
        page = result["home"]
        item = page["devices"][0]
        self.assertEqual(item["link_status"], "linked")
        self.assertEqual(item["connectivity"]["state"], "never_seen")
        self.assertNotIn(credential, repr(page))

        with connect() as conn:
            row = conn.execute(
                "SELECT identity_hash FROM home_device_runtime WHERE device_id = ?",
                (self.device_id,),
            ).fetchone()
        self.assertIsNotNone(row["identity_hash"])
        self.assertNotEqual(row["identity_hash"], credential)

    def test_heartbeat_requires_matching_credential_and_controls_online_evidence(self) -> None:
        result = link_home_device(
            self.project_id,
            self.device_id,
            capabilities=["presence", "network_status"],
        )
        credential = result["credential"]

        with self.assertRaises(PermissionError):
            record_home_heartbeat(
                self.project_id,
                self.device_id,
                credential="wrong-credential-value",
            )

        page = record_home_heartbeat(
            self.project_id,
            self.device_id,
            credential=credential,
            capabilities=["presence", "network_status"],
            reported_state={"battery": 88},
        )
        item = page["devices"][0]
        self.assertTrue(item["connectivity"]["online"])
        self.assertEqual(item["connectivity"]["state"], "online")
        self.assertEqual(item["connectivity"]["heartbeat_seq"], 1)
        self.assertEqual(item["reported_state"]["battery"], 88)

        stale = (
            datetime.now(timezone.utc)
            - timedelta(seconds=HOME_HEARTBEAT_TTL_SECONDS + 5)
        ).isoformat()
        with connect() as conn:
            conn.execute(
                "UPDATE home_device_runtime SET last_seen_at = ? WHERE device_id = ?",
                (stale, self.device_id),
            )
        page = build_nexus_home(self.project_id)
        self.assertEqual(page["devices"][0]["connectivity"]["state"], "offline")
        self.assertFalse(page["devices"][0]["connectivity"]["online"])

    def test_parental_binding_requires_explicit_link_and_capability(self) -> None:
        profile = create_parental_profile(
            self.project_id,
            child_name="Child",
            device_name="Tablet",
            daily_limit_minutes=120,
            bedtime_start="21:00",
            bedtime_end="07:00",
            blocked_categories="games",
            status="active",
        )
        profile_id = int(profile["id"])

        with self.assertRaises(ValueError):
            bind_parental_profile(self.project_id, profile_id, self.device_id)

        first = link_home_device(
            self.project_id,
            self.device_id,
            capabilities=["presence"],
        )
        with self.assertRaises(ValueError):
            bind_parental_profile(self.project_id, profile_id, self.device_id)

        linked = link_home_device(
            self.project_id,
            self.device_id,
            capabilities=["presence", "parental_policy"],
        )
        credential = linked["credential"]
        page = bind_parental_profile(self.project_id, profile_id, self.device_id)
        binding = page["parental_profiles"][0]["binding"]
        self.assertTrue(binding["explicitly_linked"])
        self.assertEqual(binding["enforcement_state"], "device_offline")
        self.assertFalse(binding["applied"])

        page = record_home_heartbeat(
            self.project_id,
            self.device_id,
            credential=credential,
            capabilities=["presence", "parental_policy"],
        )
        binding = page["parental_profiles"][0]["binding"]
        self.assertEqual(binding["enforcement_state"], "ready_for_device_agent")
        self.assertFalse(binding["applied"])
        self.assertFalse(page["policy"]["parental_rules_applied_by_server"])

    def test_unlink_revokes_identity_and_parental_eligibility(self) -> None:
        link = link_home_device(
            self.project_id,
            self.device_id,
            capabilities=["parental_policy"],
        )
        profile = create_parental_profile(
            self.project_id,
            child_name="Child",
            device_name="Tablet",
            daily_limit_minutes=60,
            bedtime_start="22:00",
            bedtime_end="07:00",
            blocked_categories="",
            status="active",
        )
        bind_parental_profile(self.project_id, int(profile["id"]), self.device_id)
        page = unlink_home_device(self.project_id, self.device_id)
        self.assertEqual(page["devices"][0]["link_status"], "revoked")
        self.assertEqual(
            page["parental_profiles"][0]["binding"]["enforcement_state"],
            "device_not_linked",
        )
        with self.assertRaises(PermissionError):
            record_home_heartbeat(
                self.project_id,
                self.device_id,
                credential=link["credential"],
            )

    def test_work_project_cannot_link_home_device_runtime(self) -> None:
        work = create_project("Work", kind="work")
        work_device = create_home_device(
            int(work["id"]),
            name="Work Device",
            device_type="computer",
            address="",
            status="offline",
            notes="",
        )
        page = build_nexus_home(int(work["id"]))
        self.assertFalse(page["enabled"])
        with self.assertRaises(ValueError):
            link_home_device(int(work["id"]), int(work_device["id"]))

    def test_link_bind_and_first_online_transition_are_audited(self) -> None:
        linked = link_home_device(
            self.project_id,
            self.device_id,
            capabilities=["parental_policy"],
        )
        profile = create_parental_profile(
            self.project_id,
            child_name="Child",
            device_name="Tablet",
            daily_limit_minutes=90,
            bedtime_start="21:30",
            bedtime_end="07:00",
            blocked_categories="",
            status="active",
        )
        bind_parental_profile(self.project_id, int(profile["id"]), self.device_id)
        record_home_heartbeat(
            self.project_id,
            self.device_id,
            credential=linked["credential"],
            capabilities=["parental_policy"],
        )
        events = list_audit_events(self.project_id, limit=50)
        event_types = {item["event_type"] for item in events}
        self.assertIn("home.device_linked", event_types)
        self.assertIn("home.parental_profile_bound", event_types)
        self.assertIn("home.device_online", event_types)


if __name__ == "__main__":
    unittest.main()
