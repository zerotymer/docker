#!/usr/bin/env python3
import json, urllib.request, urllib.parse, base64
from datetime import datetime, timedelta, UTC

# ── 설정 ──────────────────────────────────────
NEXUS_URL  = "http://localhost:8081"
NEXUS_USER = ""
NEXUS_PASS = ""

DT_URL     = "http://localhost:8082"
DT_API_KEY = ""

# 버전 전략 선택: "date" | "fixed"
VERSION_STRATEGY = "date"        # 매일 날짜 버전 생성
VERSION_FIXED    = "snapshot"    # VERSION_STRATEGY="fixed" 일 때 사용
VERSION_DATE_FMT = "%Y-%m-%d"    # 예: 2025-04-07

# 오래된 버전 자동 정리 (날짜 버전 전략일 때만 동작)
# None 으로 설정 시 정리 안 함
RETENTION_DAYS = 1              # 30일 이전 버전 자동 삭제

REPOS = [
    # parent, parent_uuid, repo, project_name
    ("maven",   "", "maven-central",    "maven-central"),
    ("npm",     "", "npm-proxy",        "npm-proxy"),
    ("pypi",    "", "pypi-proxy",       "pypi-proxy"),
    ("go",      "", "go-proxy",         "go-proxy"),
]

# ──────────────────────────────────────────────


def get_version() -> str:
    if VERSION_STRATEGY == "date":
        return datetime.now().strftime(VERSION_DATE_FMT)
    return VERSION_FIXED


# ── Nexus 헬퍼 ────────────────────────────────
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


# ── DT API 헬퍼 ───────────────────────────────
def dt_request(method: str, path: str, data: bytes = None, content_type: str = "application/json") -> dict | None:
    req = urllib.request.Request(f"{DT_URL}{path}", data=data, method=method)
    req.add_header("X-Api-Key", DT_API_KEY)
    req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"    [!] HTTP {e.code} {method} {path}: {body}")
        return None


def dt_get_project(name: str, version: str) -> dict | None:
    """프로젝트+버전으로 기존 uuid 조회"""
    encoded_name    = urllib.parse.quote(name, safe="")
    encoded_version = urllib.parse.quote(version, safe="")
    result = dt_request("GET", f"/api/v1/project/lookup?name={encoded_name}&version={encoded_version}")
    return result  # 없으면 404 → None 반환


def dt_list_project_versions(name: str) -> list:
    """프로젝트의 모든 버전 목록 반환"""
    encoded_name = urllib.parse.quote(name, safe="")
    # DT API: 프로젝트명으로 검색
    result = dt_request("GET", f"/api/v1/project?name={encoded_name}&excludeInactive=false")
    if not result:
        return []
    # API가 단일 객체 또는 리스트 반환 가능
    return result if isinstance(result, list) else [result]


def dt_delete_version(uuid: str, version_label: str) -> bool:
    """특정 프로젝트 버전 삭제"""
    result = dt_request("DELETE", f"/api/v1/project/{uuid}")
    if result is not None:
        print(f"    [✓] 버전 삭제: {version_label} (uuid: {uuid})")
        return True
    return False


def dt_upload_bom(project_name: str, version: str, sbom_bytes: bytes, parent: str, parent_uuid: str) -> bool:
    boundary = "----DTrackBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="autoCreate"\r\n\r\n'
        f"true\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="projectName"\r\n\r\n'
        f"{project_name}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="parentUUID"\r\n\r\n'
        f"{parent_uuid}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="projectVersion"\r\n\r\n'
        f"{version}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="bom"; filename="bom.json"\r\n'
        f"Content-Type: application/json\r\n\r\n"
    ).encode() + sbom_bytes + f"\r\n--{boundary}--\r\n".encode()

    result = dt_request(
        "POST", "/api/v1/bom",
        data=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    return result is not None


def dt_purge_old_versions(project_name: str, retention_days: int) -> None:
    """retention_days 이전의 날짜 버전 삭제 (DATE 전략 전용)"""
    if VERSION_STRATEGY != "date":
        return

    cutoff = datetime.now() - timedelta(days=retention_days)
    versions = dt_list_project_versions(project_name)

    for proj in versions:
        ver_str = proj.get("version", "")
        try:
            ver_date = datetime.strptime(ver_str, VERSION_DATE_FMT)
        except ValueError:
            continue  # 날짜 형식이 아닌 버전은 건드리지 않음

        if ver_date < cutoff:
            dt_delete_version(proj["uuid"], ver_str)


# ── SBOM 빌더 ─────────────────────────────────
def build_sbom(project_name: str, version: str, components: list) -> bytes:
    sbom = {
        "bomFormat":   "CycloneDX",
        "specVersion": "1.5",
        "version":     1,
        "metadata": {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "component": {
                "type":    "application",
                "name":    project_name,
                "version": version,
            },
        },
        "components": components,
    }
    return json.dumps(sbom, indent=2).encode()


# ── 메인 처리 루프 ────────────────────────────
today_version = get_version()
print(f"[*] 실행 버전: {today_version}  (전략: {VERSION_STRATEGY})")

for (parent, parent_uuid, repo, project_name) in REPOS:

    print(f"\n{'='*52}")
    print(f"[*] repo: {repo}  →  project: {project_name}  ver: {today_version}")

    # 1) 컴포넌트 수집
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
    print(f"    컴포넌트: {len(components)}개")

    if not components:
        print("    [!] 컴포넌트 없음, 스킵")
        continue

    # 2) 오늘 버전이 이미 존재하면 덮어쓰기 (재실행 멱등성 보장)
    existing = dt_get_project(project_name, today_version)
    if existing:
        print(f"    [~] 기존 버전 존재 (uuid: {existing.get('uuid')}) → 덮어쓰기")
    else:
        print(f"    [+] 신규 버전 생성")

    # 3) SBOM 생성 + 업로드
    sbom_bytes = build_sbom(project_name, today_version, components)

    sbom_path = f"/tmp/nexus-sbom-{repo}-{today_version}.cdx.json"
    with open(sbom_path, "wb") as f:
        f.write(sbom_bytes)
    print(f"    SBOM: {sbom_path}")

    if dt_upload_bom(project_name, today_version, sbom_bytes, parent, parent_uuid):
        print(f"    [✓] 업로드 완료")
    else:
        print(f"    [✗] 업로드 실패")
        continue

    # 4) 오래된 버전 정리
    if RETENTION_DAYS:
        print(f"    [*] {RETENTION_DAYS}일 이전 버전 정리 중...")
        dt_purge_old_versions(project_name, RETENTION_DAYS)

print(f"\n[완료] 전체 처리 종료  ({today_version})")
