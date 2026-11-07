#!/usr/bin/env python3
"""Makes the next App Store version (appstore/listing.json "version") if
there isn't an editable one yet, set to manual release so an approved update
only goes live when you press Release, and fills in "What's New" in every
language. Safe to run again."""
import json, sys
from pathlib import Path
sys.path.insert(0, __import__("os").path.dirname(__file__))
from appstore_upload import call, rel, BUNDLE_ID, EDITABLE, errors

listing = json.loads((Path(__file__).resolve().parent.parent / "appstore" / "listing.json").read_text())
want = listing["version"]
app_id = call("GET", f"/apps?filter[bundleId]={BUNDLE_ID}")["data"][0]["id"]
versions = call("GET", f"/apps/{app_id}/appStoreVersions?filter[platform]=IOS&limit=20")["data"]
for v in versions:
    a = v["attributes"]
    print("Existing version", a["versionString"], a.get("appStoreState") or a.get("appVersionState"))

state = lambda v: v["attributes"].get("appStoreState") or v["attributes"].get("appVersionState")
version = next((v for v in versions if state(v) in EDITABLE or v["attributes"].get("appVersionState") == "PREPARE_FOR_SUBMISSION"), None)
if version and version["attributes"]["versionString"] != want:
    vid = version["id"]
    print(f"Renaming editable version {version['attributes']['versionString']} to {want}")
    call("PATCH", f"/appStoreVersions/{vid}", {"data": {"type": "appStoreVersions", "id": vid,
         "attributes": {"versionString": want, "releaseType": "MANUAL"}}})
elif version:
    vid = version["id"]
    call("PATCH", f"/appStoreVersions/{vid}", {"data": {"type": "appStoreVersions", "id": vid, "attributes": {"releaseType": "MANUAL"}}})
    print("Version", want, "is already being prepared")
else:
    made = call("POST", "/appStoreVersions", {"data": {"type": "appStoreVersions",
                "attributes": {"platform": "IOS", "versionString": want, "releaseType": "MANUAL"},
                "relationships": {"app": rel("apps", app_id)}}})
    if not made:
        sys.exit(1)
    vid = made["data"]["id"]
    print("✓ Made version", want, vid)

locs = call("GET", f"/appStoreVersions/{vid}/appStoreVersionLocalizations")["data"]
have = {l["attributes"]["locale"]: l["id"] for l in locs}
for locale, text in listing.get("whatsNew", {}).items():
    if locale in have:
        r = call("PATCH", f"/appStoreVersionLocalizations/{have[locale]}",
                 {"data": {"type": "appStoreVersionLocalizations", "id": have[locale], "attributes": {"whatsNew": text}}})
    else:
        r = call("POST", "/appStoreVersionLocalizations",
                 {"data": {"type": "appStoreVersionLocalizations", "attributes": {"locale": locale, "whatsNew": text},
                           "relationships": {"appStoreVersion": rel("appStoreVersions", vid)}}})
    print(("✓" if r is not None else "✗"), "What's New", locale)
sys.exit(1 if errors else 0)
