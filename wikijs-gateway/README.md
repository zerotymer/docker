# wikijs-gateway

[wikijs-gateway](https://hub.docker.com/r/zerotymer/wikijs-gateway)를 실행하기 위한 기준 구성입니다. [Wiki.js](../wiki.js/README.md) GraphQL API 앞에서 페이지 조회, 검색, 구역 단위 수정, upsert를 REST와 MCP(`/mcp`)로 제공합니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다. Wiki.js는 포함하지 않으므로 [`wiki.js/`](../wiki.js/README.md)를 먼저 띄웁니다.

API는 `127.0.0.1:28081`에서만 열립니다. 읽기 API는 인증이 없으므로 외부에 열지 않습니다. 다른 호스트에서 쓰려면 [리버스 프록시](#리버스-프록시)를 앞에 둡니다.

## 이미지

| 컨테이너 | 이미지 | 컨테이너 포트 | 실행 사용자 |
|---|---|---|---|
| `wikijs-gateway` | `docker.io/zerotymer/wikijs-gateway:latest` | `8080` | `nobody` |

이미지는 `latest` 태그로 둡니다. 버전 지정은 실서버 측에서 합니다. 2026년 10월 현재 `latest`는 `1.0.5`와 같은 이미지(amd64 전용)입니다. Python 3.12, FastAPI, uvicorn으로 실행하며 `curl`, `wget`이 없습니다. 아래 설명은 이 이미지의 소스(`/app/app`)를 기준으로 합니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `example.env` | `.env`에 적을 키와 예시 |
| `wikijs-gateway.quadlets` | Podman Quadlet (볼륨, 게이트웨이) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap, Secret |
| `nginx/wikijs-gateway.conf` | Nginx `server` 블록 |
| `caddy/wikijs-gateway.caddyfile` | Caddy 사이트 블록 |

## 포트

| 호스트 | 컨테이너 | 용도 |
|---|---|---|
| `127.0.0.1:28081` | `8080` | REST API, MCP(`/mcp`), OpenAPI 문서(`/docs`) |

포트를 바꾸면 Compose `ports`, Quadlet `PublishPort`, `pod.yaml` `hostPort`, 두 프록시 설정을 함께 고칩니다.

## 엔드포인트

| 경로 | 인증 | 설명 |
|---|---|---|
| `GET /health` | 없음 | 상태. Wiki.js에 닿지 않아도 `200`이고, 본문의 `wikijsReachable`로 연결을 알림 |
| `GET /pages/by-path`, `/pages/by-uuid`, `/pages/download`, `/pages/search` | 없음 | 페이지 조회, 내려받기, 검색 |
| `POST /pages/by-paths` | 없음 | 여러 경로 한 번에 조회 (최대 50건) |
| `POST /pages/dry-run`, `/pages/patch-section`, `/pages/upsert` | `Authorization: Bearer <GATEWAY_ADMIN_TOKEN>` | 수정 미리보기, 구역 수정, 생성/덮어쓰기 |
| `/mcp` | REST와 같음 | MCP Streamable HTTP. 위 REST를 도구로 노출 (`health`, `download_page` 제외). `Authorization` 헤더를 그대로 넘겨 쓰기 도구만 토큰을 확인 |

읽기 API는 인증이 없습니다. 게이트웨이에 닿는 사람은 누구나 `WIKIJS_API_TOKEN` 권한으로 Wiki.js 페이지를 읽을 수 있습니다. 공개 포트를 `127.0.0.1`에 두고, 프록시에서도 내부망만 허용합니다.

## 환경 변수

| 키 | 기본값 | 설명 |
|---|---|---|
| `WIKIJS_GRAPHQL_URL` | `http://wikijs:3000/graphql` (kube play는 `http://wikijs-wiki:3000/graphql`) | Wiki.js GraphQL 주소 |
| `WIKIJS_API_TOKEN` | 빈 값 | Wiki.js API 키. **관리 > API 액세스**에서 API를 켜고 키를 만듦. 권한은 키의 그룹이 정함 |
| `GATEWAY_ADMIN_TOKEN` | 빈 값 | 쓰기 엔드포인트의 Bearer 토큰 |
| `TZ` | `Asia/Seoul` | 시간대 |

세 키(`WIKIJS_*`, `GATEWAY_ADMIN_TOKEN`)는 필수입니다. 키가 아예 없으면 기동하지 못하므로 `default.env`에 빈 값을 둡니다. 빈 값으로 기동하면 Wiki.js 호출은 권한 오류로 실패하고, 쓰기 요청은 모두 `401`로 거부됩니다.

| 실행 방식 | 주소 | 토큰 |
|---|---|---|
| Compose | `default.env`, `.env` | `.env`의 `WIKIJS_API_TOKEN`, `GATEWAY_ADMIN_TOKEN` |
| Quadlet | `wikijs-gateway`의 `Environment=` | podman secret `wikijs-gateway-api-token`, `wikijs-gateway-admin-token` |
| kube play | ConfigMap `wikijs-gateway` | Secret `wikijs-gateway` |

`AUDIT_DIR`, `RENDER_AFTER_WRITE`는 1.0.5 이미지가 읽지 않습니다. 감사 기록 경로는 코드에 `/audit`로 고정되어 있고, 쓰기 뒤 렌더링 옵션은 없습니다. 이미지가 이 키를 지원하게 되면 `example.env`의 주석을 풉니다.

## Wiki.js 연결

게이트웨이는 `127.0.0.1:3001`에 닿지 못합니다. 컨테이너 안의 `127.0.0.1`은 그 컨테이너 자신입니다. 대신 Wiki.js와 같은 네트워크 `wikijs-network`에 붙어 컨테이너 이름으로 접속합니다. 네트워크는 `wiki.js/` 구성이 만듭니다.

| 실행 방식 | 네트워크 | Wiki.js 주소 |
|---|---|---|
| Compose | `wiki.js/compose.yaml`의 기본 네트워크 `wikijs-network`에 `external: true`로 붙음 | `wikijs` |
| Quadlet | `wiki.js/wiki.js.quadlets`의 `wikijs.network` 유닛 | `wikijs` |
| kube play | `podman network create wikijs-network` 후 두 `pod.yaml`을 모두 `--network wikijs-network`로 실행 | `wikijs-wiki` |

## 실행

### Docker Compose

```sh
cd wiki.js && docker compose up -d && cd ..   # wikijs-network를 만든다
cd wikijs-gateway
cp example.env .env   # 토큰을 채운다
docker compose config
docker compose up -d
docker compose logs -f gateway
```

`.env` 값이 `default.env`보다 우선합니다. `wikijs-network`가 없으면 `network wikijs-network declared as external, but could not be found`로 실패합니다.

확인:

```sh
curl -fsS http://127.0.0.1:28081/health   # {"ok":true,"wikijsReachable":true}
curl -fsS "http://127.0.0.1:28081/pages/search?query=home"
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다. `wiki.js/wiki.js.quadlets`를 먼저 설치해야 `Network=wikijs.network`가 동작합니다. secret은 한 번만 만들면 재시작해도 유지됩니다.

```sh
cd wikijs-gateway
printf '%s' '<Wiki.js API 키>' | podman secret create wikijs-gateway-api-token -
openssl rand -hex 32 | tr -d '\n' | podman secret create wikijs-gateway-admin-token -
podman quadlet install wikijs-gateway.quadlets
systemctl --user daemon-reload
systemctl --user start wikijs-gateway
journalctl --user -u wikijs-gateway -f
```

관리 토큰 값은 `podman secret inspect --showsecret wikijs-gateway-admin-token`으로 확인합니다. 토큰을 바꾸려면 `podman secret rm` 후 다시 만들고 `wikijs-gateway`를 재시작합니다.

`podman quadlet install`은 이미 설치된 파일을 덮어쓰지 않습니다. `.quadlets`를 고친 뒤에는 `podman quadlet install --replace wikijs-gateway.quadlets`, `systemctl --user daemon-reload`, `systemctl --user restart wikijs-gateway` 순서로 다시 적용합니다.

### podman kube play

실행 전에 `pod.yaml`의 Secret `wikijs-gateway`에 토큰을 적습니다. 토큰을 넣은 `pod.yaml`은 커밋하지 않습니다. Wiki.js도 같은 네트워크로 실행해야 합니다.

```sh
podman network create wikijs-network
podman kube play --network wikijs-network --replace ../wiki.js/pod.yaml
podman kube play --network wikijs-network --replace pod.yaml
podman kube down pod.yaml
```

Pod 이름은 `wikijs-gateway`, 컨테이너 이름은 `wikijs-gateway-gateway`입니다. `podman kube down`은 PVC 볼륨을 지우지 않습니다. 감사 기록까지 지우려면 `podman volume rm wikijs-gateway-audit`를 실행합니다.

Quadlet과 kube play는 같은 볼륨 `wikijs-gateway-audit`를 씁니다. Compose 볼륨은 프로젝트 접두어가 붙어 `wikijs-gateway_wikijs-gateway-audit`입니다. 세 방식 모두 같은 호스트 포트를 쓰므로 동시에 실행하지 않습니다.

## 리버스 프록시

`nginx/wikijs-gateway.conf`와 `caddy/wikijs-gateway.caddyfile`은 같은 호스트 이름과 업스트림을 가리킵니다.

| 호스트 이름 | 업스트림 | 용도 |
|---|---|---|
| `wikijs-gateway.example.com` | `127.0.0.1:28081` | REST API, MCP |

호스트 이름과 인증서 경로를 실제 값으로 바꿉니다.

| 프록시 | 연결 방법 |
|---|---|
| Nginx | `nginx/wikijs-gateway.conf`를 프록시의 `conf.d/`에 복사하고 `nginx -t` 후 다시 읽기 |
| Caddy | 프록시 Caddyfile에 `import /path/to/wikijs-gateway.caddyfile`을 추가하고 `caddy validate --adapter caddyfile --config <Caddyfile>` 후 다시 읽기 |

두 파일은 같은 의미로 다음을 담습니다.

- 사이트 전체를 내부망(`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `::1`, `fc00::/7`)에서만 허용하고 나머지는 `403`입니다. 읽기 API에 인증이 없기 때문입니다. rootless Podman에서 포트 포워딩이 원본 IP를 보존하지 않으면 모든 요청이 내부 IP로 보여 차단이 무력화됩니다.
- `/mcp`는 Streamable HTTP(SSE)입니다. 응답 버퍼링을 끄고 읽기 제한 시간을 3600초로 둡니다.
- 요청 본문 제한은 16MB입니다. upsert는 페이지 전체를 보냅니다.
- TLS는 프록시에서 끝냅니다.

## 감사 기록

쓰기 요청(`patch-section`, `upsert`)마다 `/audit/<연>/<월>/<일>/<시각>_<경로>.json`과 변경이 있으면 `.diff`를 남깁니다. 기록에 실패해도 요청은 계속 처리하고 로그만 남깁니다.

| 컨테이너 | 실행 사용자 | 쓰는 경로 | 처리 |
|---|---|---|---|
| 게이트웨이 | `nobody` (`65534`) | `/audit` (이미지에서 `nobody:nogroup`) | 이름 있는 볼륨이 처음 쓸 때 이미지 소유자를 복사 |

- 볼륨에 `U`를 붙이지 않습니다. `U`는 기동할 때마다 볼륨 전체를 재귀적으로 `chown`합니다.
- 볼륨 소유권이 어긋나 `/audit`에 쓰지 못하면 한 번만 맞춥니다. rootless Podman은 `podman unshare chown -R 65534:65534 "$(podman volume inspect -f '{{.Mountpoint}}' wikijs-gateway-audit)"`입니다.
- SELinux 호스트에서는 Quadlet 마운트의 `:Z`가 데이터에 컨테이너 전용 레이블을 붙입니다. Compose 이름 있는 볼륨과 kube play PVC는 엔진이 레이블을 관리합니다.
- 감사 기록은 지우지 않고 쌓입니다. 보존 기간은 호스트에서 관리합니다.

## 주의 사항

- 상태 확인은 `/health`를 이미지에 있는 `python`으로 호출합니다. `/health`는 Wiki.js 연결과 상관없이 `200`이므로, 상태 확인은 게이트웨이 프로세스만 봅니다. Wiki.js 연결은 `wikijsReachable`로 확인합니다.
- Wiki.js 호출 제한 시간은 10초입니다(코드 고정).
- `dry-run`, `patch-section`은 요청의 `baseHash`를 현재 페이지 해시와 비교해, 그 사이 페이지가 바뀌었으면 거부합니다. `upsert`는 비교하지 않고 덮어씁니다.
- `locale`을 비우면 `ko`로 조회합니다(코드 고정).
- 이미지는 amd64만 있습니다. arm64 호스트에서는 실행되지 않습니다.
- `NoNewPrivileges`와 `NET_RAW`, `NET_ADMIN` 제거를 적용합니다.

## 참고 자료

- [Docker Hub zerotymer/wikijs-gateway](https://hub.docker.com/r/zerotymer/wikijs-gateway)
- [소스 저장소](https://github.com/zerotymer/wikijs-gateway)
- [Wiki.js GraphQL API](https://docs.requarks.io/dev/api)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
