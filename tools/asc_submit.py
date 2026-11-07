#!/usr/bin/env python3
"""Submits the version being prepared (with its Game Center achievements) for
App Review, reusing a draft submission if one is already open."""
import json, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from appstore_upload import call, rel, BUNDLE_ID, EDITABLE, errors

app_id = call("GET", f"/apps?filter[bundleId]={BUNDLE_ID}")["data"][0]["id"]
versions = call("GET", f"/apps/{app_id}/appStoreVersions?filter[platform]=IOS&limit=20")["data"]
version = next(v for v in versions if (v["attributes"].get("appStoreState") or v["attributes"].get("appVersionState")) in EDITABLE
               or v["attributes"].get("appVersionState") == "PREPARE_FOR_SUBMISSION")
vid = version["id"]
print("Version", version["attributes"]["versionString"])

subs = call("GET", f"/reviewSubmissions?filter[app]={app_id}&filter[platform]=IOS&include=items&limit=10") or {"data": []}
for s in subs["data"]:
    print("Existing submission", s["id"], s["attributes"].get("state"))
draft = next((s for s in subs["data"] if s["attributes"].get("state") == "READY_FOR_REVIEW"), None)
if not draft:
    made = call("POST", "/reviewSubmissions", {"data": {"type": "reviewSubmissions", "attributes": {"platform": "IOS"},
                                                       "relationships": {"app": rel("apps", app_id)}}})
    if not made:
        sys.exit(1)
    draft = made["data"]
    print("New submission", draft["id"])
sid = draft["id"]
items = call("GET", f"/reviewSubmissions/{sid}/items?include=appStoreVersion") or {"data": []}
has_version = any(i.get("relationships", {}).get("appStoreVersion", {}).get("data", {}) for i in items["data"])
print("Items already in it:", len(items["data"]))
if not has_version:
    r = call("POST", "/reviewSubmissionItems", {"data": {"type": "reviewSubmissionItems",
             "relationships": {"reviewSubmission": rel("reviewSubmissions", sid), "appStoreVersion": rel("appStoreVersions", vid)}}})
    print("✓ Version added" if r else "✗ Couldn't add the version (see above)")
r = call("PATCH", f"/reviewSubmissions/{sid}", {"data": {"type": "reviewSubmissions", "id": sid, "attributes": {"submitted": True}}})
print("✓ SUBMITTED FOR REVIEW" if r is not None else "✗ Not submitted (Apple's reasons above)")
sys.exit(1 if errors else 0)
