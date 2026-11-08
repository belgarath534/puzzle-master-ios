#!/usr/bin/env python3
"""Puts the newest processed build on the version being prepared, and shows
how Game Center is connected to that version (achievements for review)."""
import json, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from appstore_upload import call, rel, BUNDLE_ID, EDITABLE, errors

app_id = call("GET", f"/apps?filter[bundleId]={BUNDLE_ID}")["data"][0]["id"]
versions = call("GET", f"/apps/{app_id}/appStoreVersions?filter[platform]=IOS&limit=20")["data"]
version = next(v for v in versions if (v["attributes"].get("appStoreState") or v["attributes"].get("appVersionState")) in EDITABLE
               or v["attributes"].get("appVersionState") == "PREPARE_FOR_SUBMISSION")
vid = version["id"]
print("Version", version["attributes"]["versionString"], vid)

# The newest build that finished processing.
builds = call("GET", f"/builds?filter[app]={app_id}&sort=-uploadedDate&limit=10")["data"]
for b in builds:
    a = b["attributes"]
    print(f"  build {a.get('version')}: {a.get('processingState')}, encryption answered: {a.get('usesNonExemptEncryption')}")
ok = [b for b in builds if b["attributes"].get("processingState") == "VALID"]
if ok:
    b = ok[0]
    # Export compliance: the app only uses standard HTTPS (exempt), so answer
    # "No" if Apple is still waiting for it. Builds made after Info.plist got
    # ITSAppUsesNonExemptEncryption=false already have this answered.
    if b["attributes"].get("usesNonExemptEncryption") is None:
        r = call("PATCH", f"/builds/{b['id']}", {"data": {"type": "builds", "id": b["id"],
                 "attributes": {"usesNonExemptEncryption": False}}})
        print("✓ Export compliance answered: no non-exempt encryption" if r is not None else "✗ Couldn't answer export compliance")
    r = call("PATCH", f"/appStoreVersions/{vid}/relationships/build", {"data": {"type": "builds", "id": b["id"]}})
    print(("✓ Build " + b["attributes"]["version"] + " is on the version") if r is not None else "✗ Couldn't set the build")
else:
    print("✗ No build has finished processing yet")

# Game Center, as Apple has it.
def show(label, path):
    r = call("GET", path, ok=(200,), quiet=True)
    print(f"\n== {label}")
    print(json.dumps(r, indent=1)[:2500] if r else "  (none)")

show("version's Game Center app version", f"/appStoreVersions/{vid}/gameCenterAppVersion")
gcd = call("GET", f"/apps/{app_id}/gameCenterDetail", ok=(200,), quiet=True)
if gcd and gcd.get("data"):
    gid = gcd["data"]["id"]
    print("\n== Game Center detail relationships:", list(gcd["data"].get("relationships", {}).keys()))
    show("achievement releases", f"/gameCenterDetails/{gid}/achievementReleases?limit=3")
    show("one achievement", f"/gameCenterDetails/{gid}/gameCenterAchievements?limit=1")

# Fail the Codemagic run if no processed build could be put on the version,
# so it's obvious when to wait for Apple and run this again.
sys.exit(1 if (errors or not ok) else 0)
