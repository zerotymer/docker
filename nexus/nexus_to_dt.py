#!/usr/bin/env python3
import json, os, urllib.request, urllib.parse, base64

# ── 설정 ──────────────────────────────────────
NEXUS_URL   = "http://localhost:8081"
NEXUS_USER  = "owasp"
NEXUS_PASS  = PASSWORD

DT_URL      = "http://localhost:8082"
DT_API_KEY  = API_KEY
DT_PROJECT  = "nexus-proxy"          # DT 내 프로젝트 이름 (자동 생성됨)
DT_VERSION  = "snapshot"

# 스캔할 Nexus 프록시 리포지토리 목록
REPOS = [
    "maven-central",   # maven
    "npm-proxy",       # npm / pnpm
    "pypi-proxy",      # pip
    "go-proxy",
]

SBOM_FILE = "/tmp/nexus-sbom.cdx.json"
# ──────────────────────────────────────────────


def nexus_get(path):
    req = urllib.request.Request(f"{NEXUS_URL}{path}")
    creds = base64.b64encode(f"{NEXUS_USER}:{NEXUS_PASS}".encode()).decode()
    req.add_header("Authorization", f"Basic {creds}")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def fetch_all(repo):
    items, token = [], None
    while True:
        path = f"/service/rest/v1/components?repository={repo}"
        if token:
            path += f"&continuationToken={urllib.parse.quote(token, safe='')}"
        data = nexus_get(path)
        items.extend(data.get("items", []))
        token = data.get("continuationToken")
        if not token:
            break
    return items


def to_purl(item):
    fmt  = item.get("format", "")
    name = item.get("name", "")
    ver  = item.get("version") or "0"
    grp  = item.get("group", "")
    if fmt == "maven2" and grp:
        return f"pkg:maven/{grp}/{name}@{ver}"
    elif fmt == "npm":
        return f"pkg:npm/{name}@{ver}"
    elif fmt == "pypi":
        return f"pkg:pypi/{name}@{ver}"
    elif fmt == "nuget":
        return f"pkg:nuget/{name}@{ver}"
    elif fmt == "rubygems":
        return f"pkg:gem/{name}@{ver}"
    elif fmt == "go":
        return f"pkg:golang/{name}@{ver}"
    return None


# ── SBOM 생성 ─────────────────────────────────
seen, components = set(), []

for repo in REPOS:
    print(f"[*] 조회 중: {repo}")
    for item in fetch_all(repo):
        purl = to_purl(item)
        if not purl or purl in seen:
            continue
        seen.add(purl)
        components.append({
            "type":    "library",
            "name":    item.get("name", ""),
            "version": item.get("version", ""),
            "purl":    purl,
            "bom-ref": purl,
        })

sbom = {
    "bomFormat":   "CycloneDX",
    "specVersion": "1.5",
    "version":     1,
    "metadata": {
        "component": {
            "type":    "application",
            "name":    DT_PROJECT,
            "version": DT_VERSION,
        }
    },
    "components": components,
}

with open(SBOM_FILE, "w") as f:
    json.dump(sbom, f, indent=2)

print(f"[*] SBOM 생성 완료: {len(components)}개 컴포넌트 → {SBOM_FILE}")


# ── Dependency-Track 업로드 ───────────────────
# ── Dependency-Track 업로드 ───────────────────
import email.mime.multipart, email.mime.base, email.generator, io

print(f"[*] Dependency-Track 업로드 중...")

# multipart/form-data 직접 구성 (외부 라이브러리 없이)
boundary = "----DTrackBoundary"

with open(SBOM_FILE, "rb") as f:
    sbom_data = f.read()

body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="autoCreate"\r\n\r\n'
    f"true\r\n"
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="projectName"\r\n\r\n'
    f"{DT_PROJECT}\r\n"
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="projectVersion"\r\n\r\n'
    f"{DT_VERSION}\r\n"
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="bom"; filename="bom.json"\r\n'
    f"Content-Type: application/json\r\n\r\n"
).encode() + sbom_data + f"\r\n--{boundary}--\r\n".encode()

req = urllib.request.Request(
    f"{DT_URL}/api/v1/bom",
    data=body,
    method="POST",
)
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
req.add_header("X-Api-Key", DT_API_KEY)

try:
    with urllib.request.urlopen(req) as r:
        resp = json.loads(r.read())
        print(f"[✓] 업로드 완료")
        print(f"    결과 확인: {DT_URL}/projects")
except urllib.error.HTTPError as e:
    print(f"[!] HTTP {e.code}: {e.read().decode()}")
