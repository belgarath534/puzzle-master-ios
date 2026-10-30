#!/usr/bin/env python3
"""Puts Puzzle Master's App Store listing on App Store Connect: the text in
English, Portuguese and Spanish (appstore/listing.json), the category, the
screenshots (appstore/screenshots) and the 32 Game Center achievements with
their images (appstore/achievements.json, appstore/achievement-images).

Runs in Codemagic with the App Store Connect integration, which provides the
APP_STORE_CONNECT_* key variables. Everything already there is left alone or
updated in place, so it is safe to run again.
"""
import hashlib, json, os, sys, time
from pathlib import Path

import jwt
import requests

ROOT = Path(__file__).resolve().parent.parent / "appstore"
API = "https://api.appstoreconnect.apple.com/v1"
BUNDLE_ID = "com.puzzle.master"
SHOT_TYPES = {"iphone-6.9": "APP_IPHONE_67", "iphone-6.5": "APP_IPHONE_65", "ipad-13": "APP_IPAD_PRO_3GEN_129"}
EDITABLE = {"PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED", "INVALID_BINARY"}
errors = []


def token():
    need = ["APP_STORE_CONNECT_ISSUER_ID", "APP_STORE_CONNECT_KEY_IDENTIFIER", "APP_STORE_CONNECT_PRIVATE_KEY"]
    missing = [n for n in need if not os.environ.get(n)]
    if missing:
        print("Missing:", missing, "— App Store variables present:", sorted(k for k in os.environ if "APP_STORE" in k))
        sys.exit(1)
    now = int(time.time())
    return jwt.encode({"iss": os.environ[need[0]], "iat": now, "exp": now + 1100, "aud": "appstoreconnect-v1"},
                      private_key(os.environ[need[2]]), algorithm="ES256", headers={"kid": os.environ[need[1]], "typ": "JWT"})


def private_key(raw):
    """The .p8 key as PEM, however it was handed over: PEM, PEM with escaped
    line breaks, base64 of the PEM, a bare key body, or a path to the file."""
    import base64
    k = raw.strip().strip('"')
    if k.startswith("@file:"):
        k = k[6:]
    if os.path.isfile(k):
        k = Path(k).read_text()
    k = k.replace("\\n", "\n").replace("\r", "")
    if "BEGIN" not in k:
        try:
            decoded = base64.b64decode(k, validate=False).decode("utf-8", "ignore")
            if "BEGIN" in decoded:
                k = decoded
        except Exception:
            pass
    if "BEGIN" not in k:
        body = "".join(k.split())
        k = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(body[i:i + 64] for i in range(0, len(body), 64)) + "\n-----END PRIVATE KEY-----\n"
    elif "\n" not in k.strip():
        # One line with the markers in it: put the line breaks back.
        head, rest = k.split("-----", 2)[1], k.split("-----", 2)[2]
        body, tail = rest.rsplit("-----END", 1)
        k = f"-----{head}-----\n" + "\n".join("".join(body.split())[i:i + 64] for i in range(0, len("".join(body.split())), 64)) + "\n-----END" + tail + "\n"
    print(f"Key: {len(raw)} chars in, PEM with {k.count(chr(10))} lines")
    return k


TOKEN = None
TOKEN_AT = 0


def call(method, path, body=None, ok=(200, 201, 204), quiet=False):
    global TOKEN, TOKEN_AT
    if not TOKEN or time.time() - TOKEN_AT > 900:
        TOKEN, TOKEN_AT = token(), time.time()
    url = path if path.startswith("http") else API + path
    r = requests.request(method, url, json=body, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=60)
    if r.status_code not in ok:
        if not quiet:
            msg = f"{method} {path} -> {r.status_code}: {r.text[:600]}"
            print("  ✗", msg)
            errors.append(msg)
        return None
    return r.json() if r.content else {}


def rel(kind, id_):
    return {"data": {"type": kind, "id": id_}}


def upload(ops, data):
    for op in ops:
        chunk = data[op["offset"]:op["offset"] + op["length"]]
        hdrs = {h["name"]: h["value"] for h in op.get("requestHeaders", [])}
        r = requests.request(op["method"], op["url"], data=chunk, headers=hdrs, timeout=120)
        if r.status_code >= 300:
            raise RuntimeError(f"upload chunk -> {r.status_code}: {r.text[:200]}")


def asset(kind, attach_rel, attach_kind, attach_id, path):
    """Reserve, upload and commit a screenshot or achievement image."""
    data = path.read_bytes()
    made = call("POST", f"/{kind}", {"data": {"type": kind, "attributes": {"fileName": path.name, "fileSize": len(data)},
                                              "relationships": {attach_rel: rel(attach_kind, attach_id)}}})
    if not made:
        return False
    a = made["data"]
    try:
        upload(a["attributes"]["uploadOperations"], data)
    except Exception as e:
        print("  ✗", path.name, e)
        errors.append(f"{path.name}: {e}")
        return False
    attrs = {"uploaded": True}
    if kind == "appScreenshots":
        attrs["sourceFileChecksum"] = hashlib.md5(data).hexdigest()
    return call("PATCH", f"/{kind}/{a['id']}", {"data": {"type": kind, "id": a["id"], "attributes": attrs}}) is not None


def main():
    listing = json.loads((ROOT / "listing.json").read_text())
    apps = call("GET", f"/apps?filter[bundleId]={BUNDLE_ID}")
    if not apps or not apps["data"]:
        print(f"No app with bundle ID {BUNDLE_ID} in App Store Connect.")
        sys.exit(1)
    app_id = apps["data"][0]["id"]
    print("App", app_id)

    # The version being prepared, and its text in each language.
    versions = call("GET", f"/apps/{app_id}/appStoreVersions?filter[platform]=IOS&limit=20")["data"]
    version = next((v for v in versions if (v["attributes"].get("appStoreState") or v["attributes"].get("appVersionState")) in EDITABLE
                    or v["attributes"].get("appVersionState") == "PREPARE_FOR_SUBMISSION"), None)
    if not version:
        print("No editable App Store version found:", [(v["attributes"]["versionString"], v["attributes"].get("appStoreState")) for v in versions])
        sys.exit(1)
    vid = version["id"]
    print("Version", version["attributes"]["versionString"], vid)
    locs = {l["attributes"]["locale"]: l for l in call("GET", f"/appStoreVersions/{vid}/appStoreVersionLocalizations")["data"]}
    for locale, text in listing["localizations"].items():
        attrs = {k: text[k] for k in ("description", "keywords", "promotionalText")}
        if listing.get("urls", {}).get("support"):
            attrs["supportUrl"] = listing["urls"]["support"]
        if locale in locs:
            call("PATCH", f"/appStoreVersionLocalizations/{locs[locale]['id']}",
                 {"data": {"type": "appStoreVersionLocalizations", "id": locs[locale]["id"], "attributes": attrs}})
        else:
            made = call("POST", "/appStoreVersionLocalizations",
                        {"data": {"type": "appStoreVersionLocalizations", "attributes": {"locale": locale, **attrs},
                                  "relationships": {"appStoreVersion": rel("appStoreVersions", vid)}}})
            if made:
                locs[locale] = made["data"]
        print("✓ Text", locale)

    # Subtitle per language, and the category.
    infos = call("GET", f"/apps/{app_id}/appInfos")["data"]
    info = next((i for i in infos if (i["attributes"].get("appStoreState") or i["attributes"].get("state")) not in ("READY_FOR_SALE", "READY_FOR_DISTRIBUTION")), infos[0])
    def info_attrs(text):
        a = {"subtitle": text["subtitle"]}
        if listing.get("urls", {}).get("privacyPolicy"):
            a["privacyPolicyUrl"] = listing["urls"]["privacyPolicy"]
        return a
    ilocs = {l["attributes"]["locale"]: l for l in call("GET", f"/appInfos/{info['id']}/appInfoLocalizations")["data"]}
    for locale, text in listing["localizations"].items():
        if locale in ilocs:
            call("PATCH", f"/appInfoLocalizations/{ilocs[locale]['id']}",
                 {"data": {"type": "appInfoLocalizations", "id": ilocs[locale]["id"], "attributes": info_attrs(text)}})
        else:
            call("POST", "/appInfoLocalizations",
                 {"data": {"type": "appInfoLocalizations", "attributes": {"locale": locale, "name": "Puzzle Master", **info_attrs(text)},
                           "relationships": {"appInfo": rel("appInfos", info["id"])}}})
        print("✓ Subtitle", locale)
    c = listing["category"]
    call("PATCH", f"/appInfos/{info['id']}", {"data": {"type": "appInfos", "id": info["id"], "relationships": {
        "primaryCategory": rel("appCategories", c["primary"]),
        "primarySubcategoryOne": rel("appCategories", c["primarySubOne"]),
        "primarySubcategoryTwo": rel("appCategories", c["primarySubTwo"])}}})
    print("✓ Category", c)

    # Free, in every country.
    if listing.get("price") == "free":
        points = call("GET", f"/apps/{app_id}/appPricePoints?filter[territory]=USA&limit=200")
        free = next((p for p in (points or {"data": []})["data"] if float(p["attributes"].get("customerPrice") or 0) == 0), None)
        if free:
            made = call("POST", "/appPriceSchedules", {
                "data": {"type": "appPriceSchedules", "relationships": {
                    "app": rel("apps", app_id),
                    "baseTerritory": rel("territories", "USA"),
                    "manualPrices": {"data": [{"type": "appPrices", "id": "${price0}"}]}}},
                "included": [{"type": "appPrices", "id": "${price0}", "attributes": {"startDate": None},
                              "relationships": {"appPricePoint": rel("appPricePoints", free["id"])}}]})
            if made is not None:
                print("✓ Price: Free")
        else:
            print("  ✗ No free price point found")
        have = call("GET", f"/apps/{app_id}/appAvailabilityV2", ok=(200,), quiet=True)
        if have and have.get("data"):
            print("✓ Availability already set")
        else:
            terrs, url = [], "/territories?limit=200"
            while url:
                page = call("GET", url)
                if not page:
                    break
                terrs += [t["id"] for t in page["data"]]
                url = page.get("links", {}).get("next")
            inc = [{"type": "territoryAvailabilities", "id": f"${{{t}}}", "attributes": {"available": True},
                    "relationships": {"territory": rel("territories", t)}} for t in terrs]
            made = call("POST", "https://api.appstoreconnect.apple.com/v2/appAvailabilities", {
                "data": {"type": "appAvailabilities", "attributes": {"availableInNewTerritories": True},
                         "relationships": {"app": rel("apps", app_id),
                                           "territoryAvailabilities": {"data": [{"type": "territoryAvailabilities", "id": i["id"]} for i in inc]}}},
                "included": inc})
            if made is not None:
                print(f"✓ Available in {len(terrs)} countries and regions")

    # Age rating questionnaire, from what the riddles actually contain.
    ar = listing.get("ageRating")
    decl = call("GET", f"/appInfos/{info['id']}/ageRatingDeclaration") if ar else None
    if decl and decl.get("data"):
        current = decl["data"]["attributes"]
        attrs, unknown = {}, []
        for k, v in current.items():
            if k in ar["enums"]:
                attrs[k] = "INFREQUENT_OR_MILD" if k in ar["mild"] else "NONE"
            elif k in ar["booleans"]:
                attrs[k] = False
            elif v is None and k not in ("kidsAgeBand", "ageRatingOverride", "koreaAgeRatingOverride", "ageRatingOverrideV2"):
                unknown.append(k)
        if call("PATCH", f"/ageRatingDeclarations/{decl['data']['id']}",
                {"data": {"type": "ageRatingDeclarations", "id": decl["data"]["id"], "attributes": attrs}}) is not None:
            print("✓ Age rating:", ", ".join(f"{k}={v}" for k, v in sorted(attrs.items())))
        if unknown:
            print("  Questions still unanswered (answer them on the website):", ", ".join(unknown))

    # Screenshots, on the primary language (the others use them too).
    en = locs.get("en-US")
    if en:
        sets = {s["attributes"]["screenshotDisplayType"]: s for s in call("GET", f"/appStoreVersionLocalizations/{en['id']}/appScreenshotSets")["data"]}
        for prefix, display in SHOT_TYPES.items():
            files = sorted((ROOT / "screenshots").glob(f"{prefix}-*.png"))
            if not files:
                continue
            s = sets.get(display)
            if s is None:
                made = call("POST", "/appScreenshotSets", {"data": {"type": "appScreenshotSets", "attributes": {"screenshotDisplayType": display},
                                                                    "relationships": {"appStoreVersionLocalization": rel("appStoreVersionLocalizations", en["id"])}}})
                if not made:
                    continue
                s = made["data"]
            for old in call("GET", f"/appScreenshotSets/{s['id']}/appScreenshots")["data"]:
                call("DELETE", f"/appScreenshots/{old['id']}")
            done = sum(asset("appScreenshots", "appScreenshotSet", "appScreenshotSets", s["id"], f) for f in files)
            print(f"✓ Screenshots {display}: {done} of {len(files)}")

    # Game Center: the app's details, then each achievement in three languages with its image.
    gcd = call("GET", f"/apps/{app_id}/gameCenterDetail", ok=(200,), quiet=True)
    gcd_id = gcd["data"]["id"] if gcd and gcd.get("data") else None
    if not gcd_id:
        made = call("POST", "/gameCenterDetails", {"data": {"type": "gameCenterDetails", "relationships": {"app": rel("apps", app_id)}}})
        gcd_id = made["data"]["id"] if made else None
    if not gcd_id:
        print("Game Center isn't available for this app yet.")
    else:
        existing = {}
        url = f"/gameCenterDetails/{gcd_id}/gameCenterAchievements?limit=200"
        while url:
            page = call("GET", url)
            if not page:
                break
            for a in page["data"]:
                existing[a["attributes"]["vendorIdentifier"]] = a["id"]
            url = page.get("links", {}).get("next")
        for a in json.loads((ROOT / "achievements.json").read_text()):
            aid = existing.get(a["vendorIdentifier"])
            if not aid:
                made = call("POST", "/gameCenterAchievements", {"data": {"type": "gameCenterAchievements", "attributes": {
                    "referenceName": a["localizations"]["en-US"]["name"], "vendorIdentifier": a["vendorIdentifier"],
                    "points": a["points"], "showBeforeEarned": True, "repeatable": False},
                    "relationships": {"gameCenterDetail": rel("gameCenterDetails", gcd_id)}}})
                if not made:
                    continue
                aid = made["data"]["id"]
            have = {l["attributes"]["locale"]: l["id"] for l in (call("GET", f"/gameCenterAchievements/{aid}/localizations") or {"data": []})["data"]}
            img = ROOT / "achievement-images" / f"{a['vendorIdentifier']}.png"
            for locale, t in a["localizations"].items():
                lid = have.get(locale)
                if not lid:
                    made = call("POST", "/gameCenterAchievementLocalizations", {"data": {"type": "gameCenterAchievementLocalizations", "attributes": {
                        "locale": locale, "name": t["name"], "beforeEarnedDescription": t["description"], "afterEarnedDescription": t["description"]},
                        "relationships": {"gameCenterAchievement": rel("gameCenterAchievements", aid)}}})
                    if not made:
                        continue
                    lid = made["data"]["id"]
                cur = call("GET", f"/gameCenterAchievementLocalizations/{lid}/gameCenterAchievementImage", ok=(200,), quiet=True)
                if not (cur and cur.get("data")):
                    asset("gameCenterAchievementImages", "gameCenterAchievementLocalization", "gameCenterAchievementLocalizations", lid, img)
            print(f"✓ Achievement {a['vendorIdentifier']} ({a['points']} pts)")

    if errors:
        print(f"\n{len(errors)} problem(s):")
        for e in errors:
            print(" -", e[:300])
        sys.exit(1)
    print("\nAll done.")


if __name__ == "__main__":
    main()
