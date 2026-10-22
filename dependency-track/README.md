# dependency-track

[OWASP Dependency-Track](https://dependencytrack.org/) v5를 실행하기 위한 기준 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다. PostgreSQL은 포함하지 않으므로, 이미 있는 데이터베이스의 접속 정보를 넘깁니다.

웹 UI는 `127.0.0.1:8083`, API는 `127.0.0.1:8082`에서만 열립니다. 브라우저로 `http://127.0.0.1:8083/`을 엽니다. 프론트엔드는 정적 파일만 제공하고, 브라우저는 `API_BASE_URL`(`http://localhost:8082`)로 API에 직접 접속합니다. 다른 호스트에서 쓰려면 [리버스 프록시](#리버스-프록시)를 앞에 둡니다.

## 구성

v5에는 단일 컨테이너 이미지가 없습니다. v4의 `dependencytrack/bundled`(API+UI, 내장 H2)는 deprecated이고, v5는 PostgreSQL만 지원합니다. 이 구성은 다음 두 컨테이너를 띄웁니다. 두 이미지 모두 컨테이너 포트 `8080`을 쓰므로 한 Pod에 넣지 않습니다.

| 컨테이너 | 이미지 | 컨테이너 포트 |
|---|---|---|
| `dtrack-api` | `docker.io/dependencytrack/apiserver:latest` | `8080` API, `9000` 상태 확인, 메트릭 |
| `dtrack-frontend` | `docker.io/dependencytrack/frontend:latest` | `8080` |

이미지는 `latest` 태그로 둡니다. 버전 지정은 실서버 측에서 합니다. 설정은 v5(5.2.0) 기준입니다. 2026년 10월 현재 `latest`는 v4(4.14.5)를 가리키며 v4 유지보수가 끝나는 2026년 12월경 v5로 바뀝니다. 그 전에는 `latest`로 이 설정이 동작하지 않으므로, 실서버에서 v5 태그(예: `5.2.0`)를 지정합니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `example.env` | `.env`에 적을 키와 예시 |
| `dependency-track.quadlets` | Podman Quadlet (볼륨, API server, 프론트엔드) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap, Secret |
| `nginx/dependency-track.conf` | Nginx `server` 블록 |
| `caddy/dependency-track.caddyfile` | Caddy 사이트 블록 |

## 포트

| 호스트 | 컨테이너 | 용도 |
|---|---|---|
| `127.0.0.1:8083` | 프론트엔드 `8080` | 웹 UI |
| `127.0.0.1:8082` | API server `8080` | REST API. 브라우저의 `API_BASE_URL` |
| 기본 공개 안 함 (`127.0.0.1:9000` 주석) | API server `9000` | 상태 확인(`/health`), 메트릭(`/metrics`) |

관리 포트는 필요하면 열어도 됩니다. Quadlet `PublishPort`, Compose `ports`, `pod.yaml` `ports`의 `127.0.0.1:9000:9000` 주석을 풉니다. 메트릭은 `DT_METRICS_ENABLED=true`일 때만 나오며, 인증이 필요하면 `DT_METRICS_AUTH_USERNAME`, `DT_METRICS_AUTH_PASSWORD`를 지정합니다. 상태 확인(`HealthCmd`)은 컨테이너 안에서 호출하므로 열지 않아도 동작합니다.

`nexus`가 `127.0.0.1:8081`을 쓰므로 API를 8081로 옮기지 않습니다. `nexus/nexus_to_dt.py`는 `http://localhost:8082/api/v1/bom`으로 업로드합니다.

## 데이터베이스

PostgreSQL 14 이상이 필요합니다. 접속 정보는 다음 세 키로 넘깁니다.

| 키 | 기본값 | 설명 |
|---|---|---|
| `DT_DATASOURCE_URL` | `jdbc:postgresql://host.containers.internal:5432/dtrack` | JDBC URL |
| `DT_DATASOURCE_USERNAME` | `dtrack` | 역할 이름 |
| `DT_DATASOURCE_PASSWORD` | `dtrack` (예제 값) | 비밀번호 |

| 실행 방식 | URL, 사용자 | 비밀번호 |
|---|---|---|
| Compose | `.env` (`example.env` 참고) | `.env`의 `DT_DATASOURCE_PASSWORD` |
| Quadlet | `dtrack-api`의 `Environment=` | podman secret `dtrack-db-password` |
| kube play | ConfigMap `dtrack-api` | Secret `dtrack-db`의 `DT_DATASOURCE_PASSWORD` |

데이터베이스와 역할은 미리 만듭니다. 스키마는 API server가 시작할 때 Flyway로 만들고, 필요한 `pg_trgm` 확장도 이때 만듭니다. `pg_trgm`은 신뢰 확장이라 데이터베이스 소유자 권한이면 됩니다.

```sql
CREATE ROLE dtrack LOGIN PASSWORD '<비밀번호>';
CREATE DATABASE dtrack OWNER dtrack;
```

API server는 커넥션 풀을 기본 30개까지 엽니다. 데이터베이스 `max_connections`가 부족하면 `DT_DATASOURCE_POOL_MAX_SIZE`로 줄입니다. 데이터베이스의 `pg_hba.conf`는 컨테이너가 접속하는 주소를 허용해야 합니다.

### 같은 호스트의 PostgreSQL

`host.containers.internal`은 컨테이너에서 본 호스트 주소입니다. Podman은 자동으로 넣고, Compose는 `extra_hosts`의 `host-gateway`로 Docker에도 같은 이름을 넣습니다. 이 주소는 호스트의 루프백이 아닙니다. [`postgresql/`](../postgresql/README.md)처럼 `127.0.0.1:5432`에만 열린 데이터베이스에는 닿지 않습니다.

| 방법 | 설정 |
|---|---|
| Quadlet, rootless | `dtrack-api`의 `Network=pasta:-T,5432` 주석을 풀고 `DT_DATASOURCE_URL` 호스트를 `127.0.0.1`로 바꿈. pasta가 컨테이너 안의 `127.0.0.1:5432`를 호스트 `127.0.0.1:5432`로 넘김 |
| 그 밖의 경우 | 데이터베이스를 컨테이너가 닿는 주소(호스트 LAN 주소, 브리지 주소)에도 열고 그 주소를 `DT_DATASOURCE_URL`에 적음. 모든 인터페이스에 열지 않도록 방화벽과 `pg_hba.conf`로 제한 |

## 실행

### Docker Compose

```sh
cd dependency-track
cp example.env .env   # 접속 정보를 채운다
docker compose config
docker compose up -d
docker compose logs -f apiserver
```

첫 기동은 스키마 마이그레이션으로 수 분이 걸릴 수 있습니다. API server가 healthy가 된 뒤에 `http://127.0.0.1:8083/`을 엽니다. 취약점 데이터 동기화는 그 뒤에도 계속됩니다. 데이터베이스에 접속하지 못하면 API server가 종료되고 다시 시작됩니다.

`.env` 값이 `default.env`보다 우선합니다. 두 파일은 API server에만 들어갑니다. 프론트엔드에는 DB 비밀번호가 가지 않도록 `TZ`와 `API_BASE_URL`만 넘깁니다. `API_BASE_URL`은 Compose가 `.env`에서 읽어 채우고, 없으면 `http://localhost:8082`입니다.

확인:

```sh
curl -fsS http://127.0.0.1:8082/api/version
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다. 설치 전에 `dependency-track.quadlets`의 `DT_DATASOURCE_URL`, `DT_DATASOURCE_USERNAME`을 실제 값으로 바꿉니다. secret은 한 번만 만들면 재시작해도 유지됩니다.

```sh
cd dependency-track
printf '%s' '<비밀번호>' | podman secret create dtrack-db-password -
podman quadlet install dependency-track.quadlets
systemctl --user daemon-reload
systemctl --user start dtrack-api dtrack-frontend
journalctl --user -u dtrack-api -u dtrack-frontend -f
```

비밀번호를 바꾸려면 `podman secret rm dtrack-db-password` 후 다시 만들고 `dtrack-api`를 재시작합니다.

`podman quadlet install`은 이미 설치된 파일을 덮어쓰지 않습니다. `.quadlets`를 고친 뒤에는 `podman quadlet install --replace dependency-track.quadlets`, `systemctl --user daemon-reload`, `systemctl --user restart dtrack-api dtrack-frontend` 순서로 다시 적용합니다.

rootful로 실행할 때는 `sudo podman quadlet install dependency-track.quadlets` 후 `sudo systemctl daemon-reload`, `sudo systemctl start dtrack-api dtrack-frontend`를 사용합니다. `Network=pasta:-T,5432`는 rootless에서만 씁니다.

### podman kube play

실행 전에 `pod.yaml`의 ConfigMap `dtrack-api`에 URL과 사용자를, Secret `dtrack-db`에 비밀번호를 적습니다. 비밀번호를 넣은 `pod.yaml`은 커밋하지 않습니다.

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

Pod는 `dtrack`(API server)과 `dtrack-frontend` 두 개이고, 컨테이너 이름은 `dtrack-apiserver`, `dtrack-frontend-frontend`입니다. `podman kube down`은 PVC 볼륨을 지우지 않습니다. 데이터까지 지우려면 `podman volume rm dtrack-data`를 실행합니다.

Quadlet과 kube play는 같은 볼륨 `dtrack-data`를 씁니다. Compose 볼륨은 프로젝트 접두어가 붙어 `dependency-track_dtrack-data`입니다. 세 방식 모두 같은 호스트 포트를 쓰므로 동시에 실행하지 않습니다.

## 리버스 프록시

`nginx/dependency-track.conf`와 `caddy/dependency-track.caddyfile`은 같은 호스트 이름과 업스트림을 가리킵니다.

| 호스트 이름 | 업스트림 | 용도 |
|---|---|---|
| `dependency-track.example.com` | `127.0.0.1:8083` | 웹 UI |
| `dependency-track-api.example.com` | `127.0.0.1:8082` | API |

호스트 이름과 인증서 경로를 실제 값으로 바꿉니다. 프록시를 쓰면 `API_BASE_URL`을 브라우저가 여는 API 주소(`https://dependency-track-api.example.com`)로 바꿉니다. Compose는 `.env`, Quadlet은 `dtrack-frontend`의 `Environment=`, kube play는 ConfigMap `dtrack-frontend`를 고치고 프론트엔드를 다시 만듭니다. 이 값은 컨테이너가 시작할 때 `config.json`에 들어갑니다.

| 프록시 | 연결 방법 |
|---|---|
| Nginx | `nginx/dependency-track.conf`를 프록시의 `conf.d/`에 복사하고 `nginx -t` 후 다시 읽기 |
| Caddy | 프록시 Caddyfile에 `import /path/to/dependency-track.caddyfile`을 추가하고 `caddy validate --adapter caddyfile --config <Caddyfile>` 후 다시 읽기 |

두 파일은 같은 의미로 다음을 담습니다.

- API 본문 제한은 256MB입니다. BOM과 VEX는 API로 업로드됩니다. 더 큰 문서는 두 프록시를 함께 늘립니다.
- API 프록시의 읽기/쓰기 제한 시간은 300초입니다.
- TLS는 프록시에서 끝냅니다. `API_BASE_URL`은 `https://`로 적습니다.

API server는 기본으로 모든 출처의 CORS 요청을 허용합니다(`DT_CORS_ALLOWED_ORIGINS=*`). UI 주소만 허용하려면 `example.env`의 `DT_CORS_ALLOWED_ORIGINS`를 지정합니다.

## 소유자와 SELinux

| 컨테이너 | 실행 사용자 | 쓰는 경로 | 처리 |
|---|---|---|---|
| API server | `1000:0` | `/data` (이미지에서 `dtrack:0`, `g=u`) | 이름 있는 볼륨이 처음 쓸 때 이미지 소유자를 복사 |
| 프론트엔드 | `101` | 이미지 안의 `static/config.json`, `/etc/nginx/conf.d` | 쓰기 가능한 이미지 레이어. 마운트 없음 |

- 데이터는 이름 있는 볼륨 `dtrack-data`에 둡니다. 볼륨에 `U`를 붙이지 않습니다. `U`는 기동할 때마다 볼륨 전체를 재귀적으로 `chown`합니다.
- 볼륨 소유권이 어긋나 API server가 `/data`에 쓰지 못하면 한 번만 맞춥니다. rootless Podman은 `podman unshare chown -R 1000:0 "$(podman volume inspect -f '{{.Mountpoint}}' dtrack-data)"`입니다.
- SELinux 호스트에서는 Quadlet 마운트의 `:Z`가 데이터에 컨테이너 전용 레이블을 붙입니다. SELinux가 꺼진 호스트에서는 무시됩니다. Compose 이름 있는 볼륨과 kube play PVC는 엔진이 레이블을 관리합니다.
- 프론트엔드 엔트리포인트는 시작할 때 `static/config.json`(`API_BASE_URL`)과 `/etc/nginx/conf.d/default.conf`를 씁니다. 읽기 전용 루트 파일 시스템(`ReadOnly=true`, `read_only: true`)을 켜면 `API_BASE_URL`이 무시됩니다.

## 주의 사항

- 첫 로그인 계정은 `admin` / `admin`입니다. 첫 로그인에서 비밀번호를 바꾸라고 요청합니다.
- 프로젝트, 컴포넌트, 사용자는 PostgreSQL에, 비밀 키와 임시 파일 저장소는 `/data`에 있습니다. 데이터베이스와 `dtrack-data` 볼륨은 한 세트로 백업하고 복원합니다.
- API server 메모리 제한은 4GB입니다 (Quadlet `Memory=4g`, Compose `mem_limit`, kube play `resources.limits.memory`). 이미지 기본 `MaxRAMPercentage=80`으로 힙은 약 3.2GB입니다. 공식 문서는 API server 2GB, 4코어부터 시작하라고 안내합니다. 값을 바꾸면 세 파일을 함께 수정합니다. rootless Podman에서 메모리 제한을 쓰려면 cgroup v2의 memory 컨트롤러가 사용자에게 위임되어 있어야 합니다.
- 상태 확인은 관리 포트 `9000`의 `/health`를 이미지에 있는 BusyBox `wget`으로 호출합니다. API server 이미지에는 `curl`이 없습니다. kube play는 공식 문서대로 `/health/started`, `/health/live`를 씁니다. 첫 기동 유예는 180초입니다. Quadlet은 상태 확인이 실패하면 컨테이너를 종료해 다시 시작합니다.
- `NoNewPrivileges`와 `NET_RAW`, `NET_ADMIN` 제거를 두 컨테이너에 적용합니다.
- 실서버에서 태그를 지정할 때는 API server와 프론트엔드를 같은 버전으로 맞춥니다. 갱신 전에는 데이터베이스와 볼륨을 백업합니다.

## v4에서 옮기기

이전 구성은 v4(`dependencytrack/apiserver`, 환경 변수 `ALPINE_DATABASE_*`)였습니다. v5는 같은 데이터베이스와 데이터 디렉터리로 올려갈 수 없습니다. v4 데이터가 필요하면 [v4에서 v5로 마이그레이션](https://dependencytrack.github.io/docs/next/guides/administration/migrating-from-v4/) 문서를 따라 `dependencytrack/v4-migrator`로 새 데이터베이스에 한 번 옮깁니다. 그렇지 않으면 빈 데이터베이스로 새로 시작합니다. 이전 `docker-compose.yml`의 `./dtrack-data`(`user: '1200:1200'`)는 이 구성이 쓰지 않습니다. 마이그레이션이 끝난 뒤 지웁니다.

## 참고 자료

- [Dependency-Track 다운로드](https://dependencytrack.org/download/)
- [빠른 시작](https://dependencytrack.github.io/docs/next/tutorials/quickstart/)
- [컨테이너 이미지](https://dependencytrack.github.io/docs/next/reference/container-images/)
- [운영 배포](https://dependencytrack.github.io/docs/next/guides/administration/deploying-to-production/)
- [데이터베이스 설정](https://dependencytrack.github.io/docs/next/reference/configuration/database/)
- [설정 속성](https://dependencytrack.github.io/docs/next/reference/configuration/properties/)
- [API server Dockerfile 5.2.0](https://github.com/DependencyTrack/dependency-track/blob/5.2.0/apiserver/src/main/docker/Dockerfile)
- [프론트엔드 Dockerfile 5.2.0](https://github.com/DependencyTrack/frontend/blob/5.2.0/docker/Dockerfile.alpine)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
- [pasta](https://passt.top/builds/latest/web/passt.1.html)
