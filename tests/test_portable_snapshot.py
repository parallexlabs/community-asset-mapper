"""Focused tests for portable snapshot export (stdlib only)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export_portable_snapshot.py"


def load_module():
    spec = importlib.util.spec_from_file_location("export_portable_snapshot", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = load_module()


def base_record(**overrides):
    record = {
        "organization": {
            "id": "org-1",
            "name": "Alpha Org",
            "description": "ignored description",
            "email": "ignored@example.com",
            "website": "https://ignored.example",
            "alternate_name": "Alt",
            "provenance": {
                "source": "fixture",
                "source_id": "fix-1",
                "retrieved_at": "2024-01-01T00:00:00",
                "licence": "CC-BY-4.0",
            },
        },
        "location": {
            "id": "loc-1",
            "organization_id": "org-1",
            "name": "Main Site",
            "location_type": "physical",
            "latitude": 49.25,
            "longitude": -123.12,
            "address": {"id": "addr-1", "location_id": "loc-1", "city": "Vancouver"},
            "geocode": {"latitude": 49.25, "longitude": -123.12, "provider": "x"},
        },
        "service": {
            "id": "svc-1",
            "organization_id": "org-1",
            "location_id": "loc-1",
            "name": "Counselling",
            "description": "ignored",
            "service_type": "mental_health",
            "url": "https://ignored.example/service",
            "last_verified": "2024-06-01",
            "hours": "9-5",
            "wheelchair_accessible": True,
            "extra": {"note": "ignored"},
        },
        "source_row": {"raw_name": "secret-row", "note": "ignored"},
    }
    for key, value in overrides.items():
        record[key] = value
    return record


class PortableSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp_root = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_root.cleanup)
        self.parent = Path(self.temp_root.name).resolve() / "trusted_parent"
        self.parent.mkdir()

    def output_dir(self, name: str = "snapshot_out") -> Path:
        return self.parent / name

    def export(self, records, name: str = "snapshot_out"):
        out = self.output_dir(name)
        receipt = MOD.export_snapshot(records, out)
        return receipt, out

    def read_tables(self, out: Path):
        db_path = out / MOD.SNAPSHOT_FILENAME
        uri = db_path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            orgs = conn.execute(
                "SELECT id, name, provenance_source, provenance_source_id, "
                "provenance_retrieved_at, provenance_licence FROM organizations"
            ).fetchall()
            locs = conn.execute(
                "SELECT id, organization_id, name, location_type, latitude, longitude "
                "FROM locations"
            ).fetchall()
            svcs = conn.execute(
                "SELECT id, organization_id, location_id, name, service_type, "
                "last_verified, hours, wheelchair_accessible FROM services"
            ).fetchall()
            return orgs, locs, svcs
        finally:
            conn.close()

    def test_projection_excludes_ignored_fields(self):
        receipt, out = self.export([base_record()])
        orgs, locs, svcs = self.read_tables(out)
        self.assertEqual(len(orgs), 1)
        self.assertEqual(len(locs), 1)
        self.assertEqual(len(svcs), 1)
        self.assertNotIn("description", json.dumps(orgs))
        self.assertNotIn("ignored@example.com", json.dumps(orgs))
        self.assertNotIn("Vancouver", json.dumps(locs))
        self.assertNotIn("ignored.example/service", json.dumps(svcs))
        self.assertNotIn("secret-row", json.dumps(receipt))
        self.assertEqual(receipt["metadata_status"], "declared_not_authenticated")
        self.assertFalse(receipt["source_validated"])
        self.assertFalse(receipt["privacy_certified"])
        self.assertFalse(receipt["external_action_authorized"])
        self.assertTrue(receipt["post_write_structure_verified"])

    def test_shared_entities_collapse(self):
        second = base_record()
        second["service"] = dict(second["service"])
        second["service"]["id"] = "svc-2"
        second["service"]["name"] = "Outreach"
        receipt, _out = self.export([base_record(), second])
        self.assertEqual(receipt["organizations"], 1)
        self.assertEqual(receipt["locations"], 1)
        self.assertEqual(receipt["services"], 2)

    def test_entity_conflict_rejects(self):
        conflict = base_record()
        conflict["organization"] = dict(conflict["organization"])
        conflict["organization"]["name"] = "Different Name"
        with self.assertRaises(MOD.SnapshotError):
            MOD.normalize_records([base_record(), conflict])

    def test_non_adjacent_conflict_rejects(self):
        middle = base_record()
        middle["service"] = dict(middle["service"])
        middle["service"]["id"] = "svc-2"
        middle["service"]["name"] = "Middle"
        conflict = base_record()
        conflict["location"] = dict(conflict["location"])
        conflict["location"]["name"] = "Other Site"
        with self.assertRaises(MOD.SnapshotError):
            MOD.normalize_records([base_record(), middle, conflict])

    def test_cross_org_location_rejects(self):
        bad = base_record()
        bad["location"] = dict(bad["location"])
        bad["location"]["organization_id"] = "org-2"
        with self.assertRaises(MOD.SnapshotError):
            MOD.normalize_records([bad])

    def test_service_location_mismatch_rejects(self):
        bad = base_record()
        bad["service"] = dict(bad["service"])
        bad["service"]["location_id"] = "other-loc"
        with self.assertRaises(MOD.SnapshotError):
            MOD.normalize_records([bad])

    def test_null_false_true_zero_values(self):
        record = base_record()
        record["location"] = dict(record["location"])
        record["location"]["latitude"] = 0
        record["location"]["longitude"] = 0.0
        record["location"]["name"] = None
        record["service"] = dict(record["service"])
        record["service"]["wheelchair_accessible"] = False
        record["service"]["location_id"] = None
        unlocated = base_record()
        unlocated["location"] = dict(record["location"])
        unlocated["service"] = dict(unlocated["service"])
        unlocated["service"]["id"] = "svc-2"
        unlocated["service"]["location_id"] = None
        unlocated["service"]["wheelchair_accessible"] = None
        receipt, out = self.export([record, unlocated])
        _orgs, locs, svcs = self.read_tables(out)
        self.assertEqual(locs[0][4], 0.0)
        self.assertEqual(locs[0][5], 0.0)
        self.assertIsNone(locs[0][2])
        self.assertEqual(svcs[0][7], 0)
        self.assertIsNone(svcs[1][2])
        self.assertIsNone(svcs[1][7])
        self.assertEqual(receipt["located_services"], 0)
        self.assertEqual(receipt["unlocated_services"], 2)

    def test_unicode_and_sql_like_strings_preserved(self):
        record = base_record()
        record["organization"] = dict(record["organization"])
        record["organization"]["name"] = "Cafe \u263a; DROP TABLE organizations;--"
        record["service"] = dict(record["service"])
        record["service"]["name"] = "Service \x00unsafe"
        with self.assertRaises(MOD.SnapshotError):
            MOD.normalize_records([record])
        record["service"]["name"] = "Service ' OR 1=1 --"
        receipt, out = self.export([record])
        orgs, _l, _s = self.read_tables(out)
        self.assertIn("\u263a", orgs[0][1])
        self.assertNotIn("DROP TABLE", json.dumps(receipt))

    def test_coordinate_ranges_and_nonfinite(self):
        bad_lat = base_record()
        bad_lat["location"] = dict(bad_lat["location"])
        bad_lat["location"]["latitude"] = 91.0
        with self.assertRaises(MOD.SnapshotError):
            MOD.normalize_records([bad_lat])
        one_sided = base_record()
        one_sided["location"] = dict(one_sided["location"])
        one_sided["location"]["longitude"] = None
        with self.assertRaises(MOD.SnapshotError):
            MOD.normalize_records([one_sided])
        bool_coord = base_record()
        bool_coord["location"] = dict(bool_coord["location"])
        bool_coord["location"]["latitude"] = True
        with self.assertRaises(MOD.SnapshotError):
            MOD.normalize_records([bool_coord])

    def test_empty_list(self):
        receipt, out = self.export([])
        self.assertEqual(receipt["input_records"], 0)
        self.assertTrue((out / MOD.RECEIPT_FILENAME).is_file())

    def test_deterministic_digest_and_order(self):
        r1 = base_record()
        r2 = base_record()
        r2["service"] = dict(r2["service"])
        r2["service"]["id"] = "svc-2"
        r2["service"]["name"] = "Other"
        _, out1 = self.export([r1, r2], "snap-a")
        receipt_a, _ = self.export([r2, r1], "snap-b")
        receipt_b, _ = self.export([r1, r2], "snap-c")
        self.assertEqual(receipt_a["logical_digest"], receipt_b["logical_digest"])
        ignored_a = base_record()
        ignored_b = base_record()
        ignored_b["organization"] = dict(ignored_b["organization"])
        ignored_b["organization"]["description"] = "different ignored"
        ignored_b["source_row"] = {"x": "different"}
        d1, _ = self.export([ignored_a], "snap-d1")
        d2, _ = self.export([ignored_b], "snap-d2")
        self.assertEqual(d1["logical_digest"], d2["logical_digest"])
        self.assertTrue((out1 / MOD.SNAPSHOT_FILENAME).exists())

    def test_composite_foreign_key_rejects_cross_org_location(self):
        other = base_record()
        other["organization"] = dict(other["organization"])
        other["organization"]["id"] = "org-2"
        other["organization"]["name"] = "Beta Org"
        other["location"] = dict(other["location"])
        other["location"]["organization_id"] = "org-2"
        other["location"]["id"] = "loc-2"
        other["service"] = dict(other["service"])
        other["service"]["organization_id"] = "org-2"
        other["service"]["id"] = "svc-2"
        other["service"]["location_id"] = "loc-2"
        _receipt, out = self.export([base_record(), other], "fk-base")
        db_path = out / MOD.SNAPSHOT_FILENAME
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO services (
                        id, organization_id, location_id, name,
                        service_type, last_verified, hours, wheelchair_accessible
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("svc-bad", "org-1", "loc-2", "Bad", None, None, None, None),
                )
        finally:
            conn.close()

    def test_readonly_database_rejects_write(self):
        _receipt, out = self.export([base_record()], "ro-test")
        db_path = out / MOD.SNAPSHOT_FILENAME
        uri = db_path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("INSERT INTO organizations VALUES ('x','y',NULL,NULL,NULL,NULL)")
        finally:
            conn.close()

    def test_api_rejects_custom_object_and_cycle(self):
        class Custom:
            pass

        with self.assertRaises(MOD.SnapshotError):
            MOD.export_snapshot([Custom()], self.output_dir("custom"))
        cyclic: list[object] = []
        cyclic.append(cyclic)
        with self.assertRaises(MOD.SnapshotError):
            MOD._ensure_builtin_json(cyclic)

    def test_caps_and_deep_nesting(self):
        too_many = [base_record() for _ in range(MOD.MAX_RECORDS + 1)]
        with self.assertRaises(MOD.SnapshotError):
            MOD.normalize_records(too_many)
        long_name = base_record()
        long_name["organization"] = dict(long_name["organization"])
        long_name["organization"]["name"] = "x" * (MOD.MAX_STRING_LEN + 1)
        with self.assertRaises(MOD.SnapshotError):
            MOD.normalize_records([long_name])
        deep = {"a": 1}
        current = deep
        for _ in range(MOD.MAX_JSON_DEPTH + 2):
            current["n"] = {}
            current = current["n"]
        with self.assertRaises(MOD.SnapshotError):
            MOD._ensure_builtin_json(deep)

    def test_malformed_json_and_duplicate_keys_no_input_echo(self):
        bad_file = self.parent / "bad.json"
        bad_file.write_text('{"organization": 1}', encoding="utf-8")
        rc = MOD.main([str(bad_file), str(self.output_dir("x"))])
        self.assertEqual(rc, 2)
        dup_file = self.parent / "dup.json"
        dup_file.write_text('[{"organization":{"id":"a","id":"b","name":"n"}}]', encoding="utf-8")
        rc = MOD.main([str(dup_file), str(self.output_dir("y"))])
        self.assertEqual(rc, 2)
        nan_file = self.parent / "nan.json"
        nan_file.write_text("[NaN]", encoding="utf-8")
        rc = MOD.main([str(nan_file), str(self.output_dir("z"))])
        self.assertEqual(rc, 2)

    def test_preexisting_output_paths_rejected_without_clobber(self):
        target = self.output_dir("exists")
        target.mkdir()
        marker = target / "keep.txt"
        marker.write_text("stay", encoding="utf-8")
        with self.assertRaises(MOD.SnapshotError):
            MOD.export_snapshot([base_record()], target)
        self.assertEqual(marker.read_text(encoding="utf-8"), "stay")
        file_target = self.parent / "file_out"
        file_target.write_text("file", encoding="utf-8")
        with self.assertRaises(MOD.SnapshotError):
            MOD.export_snapshot([base_record()], file_target)

    def test_symlink_components_rejected(self):
        link_parent = self.parent / "link_parent"
        real = self.parent / "real_parent"
        real.mkdir()
        link_parent.symlink_to(real, target_is_directory=True)
        out = link_parent / "out"
        with self.assertRaises(MOD.SnapshotError):
            MOD.export_snapshot([base_record()], out)

    def test_failure_leaves_incomplete_directory_without_receipt(self):
        out = self.output_dir("incomplete")
        original_write = MOD._write_database

        def boom(*args, **kwargs):
            raise MOD.SnapshotError("forced failure")

        MOD._write_database = boom
        try:
            with self.assertRaises(MOD.SnapshotError):
                MOD.export_snapshot([base_record()], out)
        finally:
            MOD._write_database = original_write
        self.assertTrue(out.is_dir())
        self.assertFalse((out / MOD.RECEIPT_FILENAME).exists())

    def test_cli_success_and_local_input_cap(self):
        input_path = self.parent / "input.json"
        input_path.write_text(json.dumps([base_record()]), encoding="utf-8")
        out = self.output_dir("cli-out")
        huge = self.parent / "huge.json"
        with huge.open("wb") as handle:
            handle.write(b"[")
            handle.write(b" " * (MOD.MAX_INPUT_BYTES + 1))
            handle.write(b"]")
        rc = MOD.main([str(huge), str(self.output_dir("huge-out"))])
        self.assertEqual(rc, 2)
        rc = MOD.main([str(input_path), str(out)])
        self.assertEqual(rc, 0)
        self.assertTrue((out / MOD.RECEIPT_FILENAME).is_file())

    def test_no_network_invoked(self):
        input_path = self.parent / "net.json"
        input_path.write_text("[]", encoding="utf-8")
        out = self.output_dir("net-out")
        with mock.patch("socket.socket", side_effect=AssertionError("network forbidden")):
            rc = MOD.main([str(input_path), str(out)])
        self.assertEqual(rc, 0)

    def test_concurrent_reservation_only_one_winner(self):
        out = self.output_dir("race")
        barrier = threading.Barrier(2)
        results: list[str] = []
        lock = threading.Lock()

        def worker():
            barrier.wait()
            try:
                MOD.export_snapshot([], out)
                with lock:
                    results.append("ok")
            except MOD.SnapshotError:
                with lock:
                    results.append("fail")
            except OSError:
                with lock:
                    results.append("fail")

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(results), 2)
        self.assertEqual(results.count("ok"), 1)
        self.assertEqual(results.count("fail"), 1)

    def test_bool_numeric_rejected(self):
        record = base_record()
        record["service"] = dict(record["service"])
        record["service"]["wheelchair_accessible"] = 1
        with self.assertRaises(MOD.SnapshotError):
            MOD.normalize_records([record])

    def test_unknown_structural_keys_rejected(self):
        bad = base_record()
        bad["unexpected"] = 1
        with self.assertRaises(MOD.SnapshotError):
            MOD.normalize_records([bad])

    def test_mapping_subclass_rejected_without_hooks(self):
        calls = []

        class CustomDict(dict):
            def items(self):
                calls.append(True)
                return super().items()

        with self.assertRaises(MOD.SnapshotError):
            MOD.export_snapshot([CustomDict(base_record())], self.output_dir())
        self.assertEqual(calls, [])
        self.assertFalse(self.output_dir().exists())

    def test_scalar_and_list_subclasses_rejected_without_hooks(self):
        calls = []

        class CustomList(list):
            def __iter__(self):
                calls.append(True)
                return super().__iter__()

        for value in (CustomList(), type("CustomStr", (str,), {})("x")):
            with self.subTest(kind=type(value).__name__), self.assertRaises(MOD.SnapshotError):
                MOD.export_snapshot(value, self.output_dir())
        self.assertEqual(calls, [])

    def test_nested_symlink_ancestor_rejected_before_resolve(self):
        real = self.parent / "real"
        (real / "nested").mkdir(parents=True)
        link = self.parent / "link"
        link.symlink_to(real, target_is_directory=True)
        with self.assertRaises(MOD.SnapshotError):
            MOD.export_snapshot([], link / "nested" / "out")
        self.assertFalse((real / "nested" / "out").exists())

    def test_dangling_symlink_output_and_parent_traversal_rejected(self):
        link = self.output_dir("dangling")
        link.symlink_to(self.parent / "absent")
        with self.assertRaises(MOD.SnapshotError):
            MOD.export_snapshot([], link)
        self.assertTrue(link.is_symlink())
        with self.assertRaises(MOD.SnapshotError):
            MOD.export_snapshot([], self.parent / ".." / "out")

    def test_api_total_byte_cap_rejects_before_directory_creation(self):
        record = base_record()
        record["source_row"] = ["x" * 10000] * 1100
        with self.assertRaises(MOD.SnapshotError):
            MOD.export_snapshot([record], self.output_dir())
        self.assertFalse(self.output_dir().exists())

    def test_json_node_key_and_integer_limits(self):
        with mock.patch.object(MOD, "MAX_JSON_NODES", 5), self.assertRaises(MOD.SnapshotError):
            MOD._ensure_builtin_json([None] * 6)
        for value in ({"x" * (MOD.MAX_STRING_LEN + 1): None}, 2**10000):
            with self.assertRaises(MOD.SnapshotError):
                MOD._ensure_builtin_json(value)

    def test_unknown_provenance_fields_remain_null(self):
        record = base_record()
        record["organization"]["provenance"] = {}
        _receipt, out = self.export([record])
        orgs, _locations, _services = self.read_tables(out)
        self.assertEqual(orgs[0][2:], (None, None, None, None))

    def test_invalid_unicode_is_controlled_before_output(self):
        record = base_record()
        record["service"]["name"] = "\ud800"
        with self.assertRaises(MOD.SnapshotError):
            MOD.export_snapshot([record], self.output_dir())
        self.assertFalse(self.output_dir().exists())

    def test_cli_input_symlink_and_deep_json_do_not_echo(self):
        original = self.parent / "plain.json"
        original.write_text("[]", encoding="utf-8")
        link = self.parent / "linked.json"
        link.symlink_to(original)
        deep = self.parent / "deep.json"
        deep.write_text("[" * 2000 + "0" + "]" * 2000, encoding="utf-8")
        for source in (link, deep):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                rc = MOD.main([str(source), str(self.output_dir())])
            self.assertEqual(rc, 2)
            self.assertEqual(err.getvalue(), "export failed\n")
            self.assertFalse(self.output_dir().exists())
        self.assertEqual(original.read_text(), "[]")

    def test_cli_reads_at_most_byte_cap_plus_one(self):
        source = self.parent / "large.json"
        source.write_bytes(b"[]" + b" " * 100)
        with mock.patch.object(MOD, "MAX_INPUT_BYTES", 10):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(MOD.main([str(source), str(self.output_dir())]), 2)
            self.assertEqual(err.getvalue(), "export failed\n")
        self.assertFalse(self.output_dir().exists())

    def test_post_write_selected_value_corruption_prevents_receipt(self):
        original = MOD._write_database

        def corrupt(db, *rows):
            original(db, *rows)
            with sqlite3.connect(db) as connection:
                connection.execute("UPDATE services SET name = 'Changed synthetic'")

        with (
            mock.patch.object(MOD, "_write_database", side_effect=corrupt),
            self.assertRaises(MOD.SnapshotError),
        ):
            MOD.export_snapshot([base_record()], self.output_dir())
        self.assertTrue(self.output_dir().exists())
        self.assertFalse((self.output_dir() / MOD.RECEIPT_FILENAME).exists())

    def test_cli_sqlite_failure_is_generic_and_leaves_no_receipt(self):
        source = self.parent / "empty.json"
        source.write_text("[]", encoding="utf-8")
        with (
            mock.patch.object(
                MOD, "_write_database", side_effect=sqlite3.OperationalError("Synthetic marker")
            ),
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            self.assertEqual(MOD.main([str(source), str(self.output_dir())]), 2)
        self.assertEqual(err.getvalue(), "export failed\n")
        self.assertFalse((self.output_dir() / MOD.RECEIPT_FILENAME).exists())

    def test_conflicting_service_and_key_order(self):
        first = base_record()
        other = base_record()
        other["service"]["hours"] = "Different"
        with self.assertRaises(MOD.SnapshotError):
            MOD.export_snapshot([first, other], self.output_dir())
        reversed_keys = json.loads(json.dumps(first, sort_keys=True))
        left, _out = self.export([first], "left")
        right, _out = self.export([reversed_keys], "right")
        self.assertEqual(left["logical_digest"], right["logical_digest"])


if __name__ == "__main__":
    unittest.main()
