# llm-registry

LLM Registry(`context-ref-registry`)를 실행하기 위한 기준 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다. Compose와 kube play는 PostgreSQL을 함께 띄웁니다. Quadlet은 PostgreSQL을 포함하지 않으므로, 별도로 띄운 데이터베이스의 접속 정보를 `DATABASE_URL`로 넘깁니다.

웹 UI는 `127.0.0.1:3030`, API는 `127.0.0.1:8000`에서만 열립니다. 브라우저로 `http://127.0.0.1:3030/`을 엽니다. 다른 호스트에서 쓰려면 [리버스 프록시](#리버스-프록시)를 앞에 둡니다.

## 구성

| 컨테이너 | 이미지 | 컨테이너 포트 | 역할 |
|---|---|---|---|
| `llm-registry-db` | `docker.io/library/postgres:latest` | `5432` | 데이터베이스. Compose, kube play만 |
| `llm-registry-api` | `docker.io/zerotymer/llm-registry-api:latest` | `8000` | FastAPI. REST, MCP(`/mcp/`), `/health` |
| `llm-registry-front` | `docker.io/zerotymer/llm-registry-front:latest` | `3000` | Next.js. 웹 UI, 에이전트 API 게이트웨이(`/api/v1/*`), MCP 게이트웨이(`/api/v1/mcp`) |

브라우저와 에이전트는 프론트엔드에만 접속합니다. 프론트엔드가 서버 쪽에서 `BACKEND_API_URL`로 API를 호출합니다. 이 값은 브라우저에 나가지 않으므로 컨테이너끼리 닿는 주소를 적습니다.

| 실행 방식 | `BACKEND_API_URL` | API의 DB 호스트 |
|---|---|---|
| Compose | `http://api:8000` | `postgres` |
| Quadlet (한 Pod) | `http://127.0.0.1:8000` | `postgres` (`postgres-network`) |
| kube play (한 Pod) | `http://127.0.0.1:8000` | `127.0.0.1` |

이미지는 `latest` 태그로 둡니다. 버전 지정은 실서버 측에서 합니다. `postgres:latest`는 2026년 10월 현재 18입니다. 18부터 데이터 위치가 `/var/lib/postgresql/18/docker`로 바뀌어 볼륨을 `/var/lib/postgresql`에 마운트합니다. 실서버에서 17 이하로 고정하면 마운트 경로를 `/var/lib/postgresql/data`로 바꿉니다.

원본 저장소의 `backup` 서비스(`pg_dump` 일정 실행)는 게시된 이미지가 없어 넣지 않았습니다. [백업](#백업)을 참고합니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능). PostgreSQL과 API에만 들어감 |
| `example.env` | `.env`에 적을 키와 예시 |
| `llm-registry.quadlets` | Podman Quadlet (Pod, API, 프론트엔드). PostgreSQL 없음 |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap, Secret |
| `nginx/llm-registry.conf` | Nginx `server` 블록 |
| `caddy/llm-registry.caddyfile` | Caddy 사이트 블록 |

## 포트

| 호스트 | 컨테이너 | 용도 |
|---|---|---|
| `127.0.0.1:3030` | 프론트엔드 `3000` | 웹 UI, `/api/v1/*`, `/api/v1/mcp` |
| `127.0.0.1:8000` | API `8000` | REST 직접 호출, `/docs`, `/mcp/` |
| 공개 안 함 | PostgreSQL `5432` | Compose 네트워크, Pod 안에서만 접속 |

`gitea`, `adguard`가 `127.0.0.1:3000`을 쓰므로 웹 UI는 `3030`에 둡니다. 이전 `docker-compose.yml`은 `3000`, `8000`을 모든 인터페이스에 공개했습니다. API 포트는 로컬 개발용입니다. 필요 없으면 세 파일에서 함께 지웁니다. 프론트엔드는 Compose 네트워크나 Pod 안에서 API에 닿으므로 영향이 없습니다.

## 환경 변수

| 키 | 기본값 | 대상 | 설명 |
|---|---|---|---|
| `POSTGRES_DB` | `llmref` | PostgreSQL | 볼륨이 비어 있을 때 만드는 데이터베이스 |
| `POSTGRES_USER` | `llmref` | PostgreSQL | 볼륨이 비어 있을 때 만드는 역할 |
| `POSTGRES_PASSWORD` | `llmref` (예제 값) | PostgreSQL | 위 역할의 비밀번호 |
| `DATABASE_URL` | `postgresql+asyncpg://llmref:llmref@postgres:5432/llmref` | API | SQLAlchemy asyncpg URL |
| `JWT_SECRET` | 없음 | API | 비우면 기동할 때마다 새로 만듦 |
| `BACKEND_API_URL` | 실행 방식마다 다름 | 프론트엔드 | 서버 쪽 API 주소 |

`DATABASE_URL`의 사용자, 비밀번호, 데이터베이스는 `POSTGRES_*`와 같게 둡니다. 비밀번호는 URL에 들어가므로 영문과 숫자로 만듭니다(`openssl rand -hex 24`). 특수 문자를 쓰면 URL 인코딩합니다. `POSTGRES_*`는 볼륨을 처음 만들 때만 적용됩니다. 그 뒤에 비밀번호를 바꾸려면 `ALTER ROLE llmref PASSWORD '...'`로 바꾸고 `DATABASE_URL`을 맞춥니다.

| 실행 방식 | `POSTGRES_PASSWORD` | `DATABASE_URL` |
|---|---|---|
| Compose | `.env` | `.env` |
| Quadlet | 별도 PostgreSQL에서 관리 | `llm-registry-api`의 `Environment=DATABASE_URL` |
| kube play | Secret `llm-registry-db` | Secret `llm-registry-db` |

## 실행

### Docker Compose

```sh
cd llm-registry
cp example.env .env   # 비밀번호를 채운다
docker compose config
docker compose up -d
docker compose logs -f api
```

`.env` 값이 `default.env`보다 우선합니다. 두 파일은 PostgreSQL과 API에만 들어갑니다. 프론트엔드에는 DB 비밀번호가 가지 않도록 `TZ`와 `BACKEND_API_URL`만 넘깁니다. 기동 순서는 PostgreSQL healthy → API healthy → 프론트엔드입니다.

외부 PostgreSQL을 쓰려면 `.env`의 `DATABASE_URL`을 그 주소로 바꾸고 `docker compose up -d --no-deps api frontend`로 띄웁니다. `--no-deps`가 없으면 `depends_on` 때문에 `postgres`도 함께 뜹니다.

확인:

```sh
curl -fsS http://127.0.0.1:8000/health
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3030/login
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다. Quadlet은 PostgreSQL을 포함하지 않습니다. 데이터베이스와 역할을 미리 만듭니다. 스키마는 API가 시작할 때 만듭니다.

```sql
CREATE ROLE llmref LOGIN PASSWORD '<비밀번호>';
CREATE DATABASE llmref OWNER llmref;
```

설치 전에 `llm-registry-api`의 `Environment=DATABASE_URL`을 실제 값으로 바꿉니다. 비밀번호를 넣은 `.quadlets`는 커밋하지 않습니다.

| 데이터베이스 위치 | `[Pod]` 설정 | `DATABASE_URL` 호스트 |
|---|---|---|
| [`postgresql/`](../postgresql/README.md) Quadlet (기본) | `Network=postgres.network` | `postgres` (컨테이너 이름) |
| 같은 호스트의 `127.0.0.1:5432`, rootless | `Network=` 줄 대신 `Network=pasta:-T,5432` | `127.0.0.1` |
| 다른 호스트 | `Network=` 줄 삭제 | 그 호스트 주소 |

`postgres.network`를 쓰면 `postgresql/postgresql.quadlets`를 먼저 설치해 `postgres-network`가 있어야 합니다. API는 데이터베이스에 접속하지 못하면 마이그레이션에서 종료되고 `Restart=on-failure`로 다시 시도합니다.

```sh
cd llm-registry
podman quadlet install llm-registry.quadlets
systemctl --user daemon-reload
systemctl --user start llm-registry-pod
journalctl --user -u llm-registry-api -u llm-registry-front -f
```

`llm-registry-pod`를 시작하면 API와 프론트엔드가 함께 시작합니다. 세션을 재시작 뒤에도 유지하려면 `llm-registry-jwt-secret` secret을 만들고 `llm-registry-api`의 `Secret=` 주석을 풉니다.

`podman quadlet install`은 이미 설치된 파일을 덮어쓰지 않습니다. `.quadlets`를 고친 뒤에는 `podman quadlet install --replace llm-registry.quadlets`, `systemctl --user daemon-reload`, `systemctl --user restart llm-registry-pod` 순서로 다시 적용합니다.

rootful로 실행할 때는 `sudo podman quadlet install llm-registry.quadlets` 후 `sudo systemctl daemon-reload`, `sudo systemctl start llm-registry-pod`를 사용합니다.

### podman kube play

실행 전에 `pod.yaml`의 Secret `llm-registry-db`에 비밀번호를 적습니다. `POSTGRES_PASSWORD`와 `DATABASE_URL`의 비밀번호를 같게 둡니다. 비밀번호를 넣은 `pod.yaml`은 커밋하지 않습니다.

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

컨테이너 이름은 `llm-registry-postgres`, `llm-registry-api`, `llm-registry-frontend`입니다. kube play는 컨테이너 시작 순서를 기다리지 않습니다. API가 PostgreSQL보다 먼저 뜨면 마이그레이션에서 종료되고 `restartPolicy: Always`로 다시 시작합니다. `podman kube down`은 PVC 볼륨을 지우지 않습니다. 데이터까지 지우려면 `podman volume rm llm-registry-db`를 실행합니다.

kube play 볼륨은 `llm-registry-db`, Compose 볼륨은 프로젝트 접두어가 붙어 `llm-registry_llm-registry-db`입니다. 세 방식 모두 같은 호스트 포트를 쓰므로 동시에 실행하지 않습니다.

## 리버스 프록시

`nginx/llm-registry.conf`와 `caddy/llm-registry.caddyfile`은 같은 호스트 이름과 업스트림을 가리킵니다. 프론트엔드만 공개하고 API 포트는 공개하지 않습니다.

| 호스트 이름 | 업스트림 | 경로 |
|---|---|---|
| `llm-registry.example.com` | `127.0.0.1:3030` | `/` 웹 UI, `/api/v1/*` 에이전트 API, `/api/v1/mcp` MCP |

호스트 이름과 인증서 경로를 실제 값으로 바꿉니다.

| 프록시 | 연결 방법 |
|---|---|
| Nginx | `nginx/llm-registry.conf`를 프록시의 `conf.d/`에 복사하고 `nginx -t` 후 다시 읽기 |
| Caddy | 프록시 Caddyfile에 `import /path/to/llm-registry.caddyfile`을 추가하고 `caddy validate --adapter caddyfile --config <Caddyfile>` 후 다시 읽기 |

두 파일은 같은 의미로 다음을 담습니다.

- 요청 본문 제한은 32MB입니다. 큰 ingest 요청을 보내면 두 프록시를 함께 늘립니다.
- `/api/v1/mcp`는 streamable-http(SSE)입니다. 응답을 버퍼링하지 않고, 읽기/쓰기 제한 시간을 3600초로 둡니다.
- TLS는 프록시에서 끝냅니다.

MCP 클라이언트에는 `https://llm-registry.example.com/api/v1/mcp`와 API 키를 등록합니다.

## 소유자와 SELinux

| 컨테이너 | 실행 사용자 | 쓰는 경로 | 처리 |
|---|---|---|---|
| PostgreSQL | root로 시작해 `postgres(999)` | `/var/lib/postgresql` | 엔트리포인트가 chown |
| API | root | 없음 | 마운트 없음 |
| 프론트엔드 | `nextjs(1001)` | 없음 | 마운트 없음 |

- 데이터는 이름 있는 볼륨 `llm-registry-db`에 둡니다. 볼륨에 `U`를 붙이지 않습니다.
- Compose 이름 있는 볼륨과 kube play PVC는 엔진이 SELinux 레이블을 관리합니다. Quadlet은 데이터를 별도 PostgreSQL에 둡니다.

## 백업

PostgreSQL 컨테이너에서 `pg_dump`로 받습니다.

```sh
docker exec llm-registry-db pg_dump -U llmref -d llmref -Fc > llm-registry.dump        # Compose
podman exec postgres pg_dump -U llmref -d llmref -Fc > llm-registry.dump               # Quadlet (postgresql/)
podman exec llm-registry-postgres pg_dump -U llmref -d llmref -Fc > llm-registry.dump  # kube play
```

## 주의 사항

- 첫 로그인 계정은 `admin` / `admin`입니다. 이미지에 고정되어 있어 환경 변수로 바꿀 수 없습니다. 첫 로그인 뒤 바로 비밀번호를 바꿉니다.
- `JWT_SECRET`을 지정하지 않으면 엔트리포인트가 기동할 때마다 새로 만듭니다. 재시작하면 모든 로그인 세션이 끊깁니다.
- API는 시작할 때 `alembic upgrade head`로 스키마를 만들거나 올립니다. 이미지를 갱신하기 전에 데이터베이스를 백업합니다.
- API와 프론트엔드는 같은 버전으로 맞춥니다.
- `NoNewPrivileges`와 `NET_RAW`, `NET_ADMIN` 제거를 모든 컨테이너에 적용합니다.
- 상태 확인: PostgreSQL은 `pg_isready`, API는 `python`으로 `/health`(이미지에 `curl`, `wget`이 없음), 프론트엔드는 BusyBox `wget`으로 `/login`을 호출합니다. Quadlet은 상태 확인이 실패하면 컨테이너를 종료해 다시 시작합니다.

## 이전 구성에서 옮기기

이전 `docker-compose.yml`은 `postgres:16-alpine`, 데이터베이스 `llm-reg`, 사용자 `user`, 볼륨 `llm-registry_postgres_data`를 썼고, 상태 확인이 존재하지 않는 사용자 `llmref`를 확인했습니다. 이 구성은 PostgreSQL 18, `llmref`, 새 볼륨을 씁니다. 주 버전이 달라 데이터 디렉터리를 그대로 쓸 수 없으므로 덤프로 옮깁니다.

```sh
# 이전 구성이 떠 있는 상태에서 (이전 컨테이너 이름은 docker ps로 확인)
docker exec llm-registry-postgres-1 pg_dump -U user -d llm-reg -Fc -O -x > old.dump
docker stop llm-registry-postgres-1 llm-registry-api-1 llm-registry-frontend-1
# 새 구성을 띄운 뒤 (API가 마이그레이션을 끝낸 다음)
docker compose stop api frontend
docker exec -i llm-registry-db pg_restore -U llmref -d llmref --clean --if-exists -O -x < old.dump
docker compose start api frontend
```

옮긴 뒤 이전 볼륨은 `docker volume rm llm-registry_postgres_data`로 지웁니다.

## 참고 자료

- [postgres 이미지](https://hub.docker.com/_/postgres)
- [Next.js standalone 출력](https://nextjs.org/docs/app/api-reference/config/next-config-js/output)
- [MCP streamable-http](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
