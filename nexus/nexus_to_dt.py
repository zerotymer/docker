#!/usr/bin/env python3
import json, os, urllib.request, urllib.parse, base64, tempfile

# ── 설정 ──────────────────────────────────────
NEXUS_URL  = "http://localhost:8081"
NEXUS_USER = ""
NEXUS_PASS = ""

DT_URL     = "http://localhost:8082"
DT_API_KEY = ""
DT_VERSION = "snapshot"

REPOS = [
    # parent, parent_uuid, repo, project_name
    ("maven",   "", "maven-central",    "maven-central"),
    ("npm",     "", "npm-proxy",        "npm-proxy"),
    ("pypi",    "", "pypi-proxy",       "pypi-proxy"),
    ("go",      "", "go-proxy",         "go-proxy"),
    ]

# ──────────────────────────────────────────────


def nexus_get(path: str) -> dict:
    req = urllib.request.Request(f"{NEXUS_URL}{path}")
    creds = base64.b64encode(f"{NEXUS_USER}:{NEXUS_PASS}".encode()).decode()
    req.add_header("Authorization", f"Basic {creds}")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def fetch_all(repo: str) -> list:
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


def to_purl(item: dict) -> str | None:
    fmt  = item.get("format", "")
    name = item.get("name", "")
    ver  = item.get("version") or "0"
    grp  = item.get("group", "")
    mapping = {
        "maven2":   lambda: f"pkg:maven/{grp}/{name}@{ver}" if grp else None,
        "npm":      lambda: f"pkg:npm/{name}@{ver}",
        "pypi":     lambda: f"pkg:pypi/{name}@{ver}",
        "nuget":    lambda: f"pkg:nuget/{name}@{ver}",
        "rubygems": lambda: f"pkg:gem/{name}@{ver}",
        "go":       lambda: f"pkg:golang/{name}@{ver}",
    }
    builder = mapping.get(fmt)
    return builder() if builder else None


def build_sbom(project_name: str, components: list) -> dict:
    return {
        "bomFormat":   "CycloneDX",
        "specVersion": "1.5",
        "version":     1,
        "metadata": {
            "component": {
                "type":    "application",
                "name":    project_name,
                "version": DT_VERSION,
            }
        },
        "components": components,
    }


#def upload_to_dt(sbom_bytes: bytes, project_name: str) -> None:
def upload_to_dt(sbom_bytes: bytes, project_name: str, parent: str, parent_uuid: str) -> None:
    boundary = "----DTrackBoundary"

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="autoCreate"\r\n\r\n'
        f"true\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="projectName"\r\n\r\n'
        f"{project_name}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="projectVersion"\r\n\r\n'
        f"{DT_VERSION}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="parentUUID"\r\n\r\n'
        f"{parent_uuid}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="bom"; filename="bom.json"\r\n'
        f"Content-Type: application/json\r\n\r\n"
    ).encode() + sbom_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{DT_URL}/api/v1/bom",
        data=body,
        method="POST",
    )
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("X-Api-Key", DT_API_KEY)

    try:
        with urllib.request.urlopen(req) as r:
            json.loads(r.read())
            print(f"    [✓] 업로드 완료 → {parent}/{project_name} - {parent_uuid}")
    except urllib.error.HTTPError as e:
        print(f"    [!] HTTP {e.code}: {e.read().decode()}")


# ── 리포지토리별 처리 루프 ─────────────────────
for (parent, parent_uuid, repo, project_name) in REPOS:


    print(f"\n{'='*50}")
    print(f"[*] 리포지토리: {repo}  →  DT 프로젝트: {project_name}")

    # 1) Nexus에서 컴포넌트 수집
    seen, components = set(), []
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

    print(f"    컴포넌트 수: {len(components)}개")

    if not components:
        print(f"    [!] 컴포넌트 없음, 스킵")
        continue

    # 2) SBOM 생성 (메모리 내)
    sbom      = build_sbom(project_name, components)
    sbom_bytes = json.dumps(sbom, indent=2).encode()

    # 필요 시 파일로도 저장
    sbom_path = f"/tmp/nexus-sbom-{repo}.cdx.json"
    with open(sbom_path, "wb") as f:
        f.write(sbom_bytes)
    print(f"    SBOM 저장: {sbom_path}")

    # 3) Dependency-Track 업로드
    print(f"    [*] DT 업로드 중...")
    upload_to_dt(sbom_bytes, project_name, parent, parent_uuid)

print(f"\n[완료] 전체 처리 종료")
