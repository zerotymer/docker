# wiki.js

[Wiki.js](https://js.wiki/) 2.x를 실행하기 위한 기준 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다. 데이터베이스는 이미 있는 PostgreSQL을 쓰는 것이 기본이며, Compose에서는 `postgres` 프로필로 PostgreSQL을 함께 띄울 수 있습니다.

웹 UI는 `127.0.0.1:3001`에서만 열립니다. 브라우저로 `http://127.0.0.1:3001/`을 열면 첫 화면에서 관리자 계정과 사이트 주소를 설정합니다. 다른 호스트에서 쓰려면 [리버스 프록시](#리버스-프록시)를 앞에 둡니다.

## 이미지

| 컨테이너 | 이미지 | 컨테이너 포트 |
|---|---|---|
| `wikijs` | `ghcr.io/requarks/wiki:latest` | `3000` |
| `wikijs-postgres` (`postgres` 프로필) | `docker.io/library/postgres:latest` | `5432` (공개 안 함) |

이미지는 `latest` 태그로 둡니다. 버전 지정은 실서버 측에서 합니다. 2026년 10월 현재 `latest`는 `2`, `2.5`와 같은 이미지(2.5.316, 2026-10-02 빌드)를 가리키며, 설정은 2.x 기준입니다. 이 이미지의 `/wiki/config.yml`은 아래 [참고 자료](#참고-자료)의 v2.5.314 `dev/build/config.yml`과 내용이 같습니다. 3.x는 `3.0.0-beta`, `3.0.0-beta.*` 같은 시험판 태그만 있고 `3` 태그는 없습니다. 같은 이미지가 `docker.io/requarks/wiki`에도 올라가며 태그와 다이제스트가 같습니다. 공식 문서를 따라 `ghcr.io`를 씁니다. 3.x는 PostgreSQL만 지원하고 `DB_TYPE` 대신 `DB_SCHEMA`를 읽는 등 설정이 다르므로, `latest`가 3.x로 바뀌면 이 구성을 다시 확인합니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose (`postgres` 프로필로 PostgreSQL 포함) |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `example.env` | `.env`에 적을 키와 예시 |
| `wiki.js.quadlets` | Podman Quadlet (볼륨, 네트워크 `wikijs-network`, Wiki.js) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap, Secret |
| `nginx/wiki.js.conf` | Nginx `server` 블록 |
| `caddy/wiki.js.caddyfile` | Caddy 사이트 블록 |

이전 `docker-compose.yml`, `docker-compose-with-postgre.yml`, `config.yml`은 지웠습니다. 존재하지 않는 `ghcr.io/requarks/wiki:3` 태그를 썼고, `config.yml`의 `127.0.0.1`은 컨테이너 자신을 가리켜 데이터베이스에 닿지 않았습니다. 지금은 이미지에 들어 있는 `/wiki/config.yml`이 `DB_*` 환경 변수를 읽습니다.

## 포트

| 호스트 | 컨테이너 | 용도 |
|---|---|---|
| `127.0.0.1:3001` | Wiki.js `3000` | 웹 UI, GraphQL API |

`gitea`, `adguard`가 `127.0.0.1:3000`을 쓰므로 `3001`로 엽니다. 포트를 바꾸면 Compose `ports`, Quadlet `PublishPort`, `pod.yaml` `hostPort`, 두 프록시 설정을 함께 고칩니다. 내장 HTTPS(`3443`, `SSL_ACTIVE`)는 쓰지 않습니다. TLS는 프록시에서 끝냅니다.

## 데이터베이스

접속 정보는 다음 키로 넘깁니다. 이미지의 `/wiki/config.yml`이 이 값을 읽습니다.

| 키 | 기본값 | 설명 |
|---|---|---|
| `DB_TYPE` | `postgres` | `postgres`, `mysql`, `mariadb`, `mssql` |
| `DB_HOST` | `host.containers.internal` (Quadlet은 `postgres`) | 호스트 이름 |
| `DB_PORT` | `5432` | 포트 |
| `DB_USER` | `wikijs` | 역할 이름 |
| `DB_PASS` | `wikijs` (예제 값) | 비밀번호 |
| `DB_NAME` | `wiki` | 데이터베이스 이름 |
| `DB_SSL` | 없음 | `true`면 TLS로 접속 |

이미지의 `/wiki/config.yml`은 `$(이름)` 자리를 같은 이름의 환경 변수로 바꾼 뒤 YAML로 읽습니다. 2.5 이미지가 읽는 키는 `DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME`, `DB_FILEPATH`(SQLite), `DB_SSL`, `SSL_ACTIVE`, `LETSENCRYPT_DOMAIN`, `LETSENCRYPT_EMAIL`, `LOG_LEVEL`, `LOG_FORMAT`, `HA_ACTIVE`입니다. 코드가 직접 읽는 `DB_PASS_FILE`(파일에서 비밀번호), `DB_SSL_CA`, `CONFIG_FILE`도 있습니다. `DB_SCHEMA`는 3.x 키라 2.x에서는 무시됩니다.

`LOG_LEVEL`, `LOG_FORMAT` 말고는 기본값이 없습니다. 비워 두면 문자열 `undefined`가 들어갑니다. `DB_SSL`, `SSL_ACTIVE`, `HA_ACTIVE`는 `true`일 때만 켜지므로 비워 둬도 되지만, `DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`은 반드시 지정합니다.

값은 YAML 텍스트에 그대로 끼워진 뒤 파싱됩니다. `/wiki/config.yml`이 `pass: '$(DB_PASS)'`처럼 작은따옴표로 감싸므로, 비밀번호에 `'`가 들어가면 YAML이 깨져 기동하지 못합니다. 비밀번호는 `openssl rand -hex 32`처럼 영숫자로 만듭니다. 따옴표가 필요하면 `DB_PASS` 대신 `DB_PASS_FILE`로 파일 경로를 넘깁니다. 이 값은 YAML을 거치지 않습니다.

| 실행 방식 | 호스트, 사용자 | 비밀번호 |
|---|---|---|
| Compose | `.env` (`example.env` 참고) | `.env`의 `DB_PASS` |
| Quadlet | `wikijs`의 `Environment=` | podman secret `wikijs-db-password` |
| kube play | ConfigMap `wikijs` | Secret `wikijs-db`의 `DB_PASS` |

데이터베이스와 역할은 미리 만듭니다. 스키마는 Wiki.js가 시작할 때 만듭니다. PostgreSQL 15부터 `public` 스키마에 아무나 테이블을 만들 수 없으므로 데이터베이스 소유자를 `wikijs`로 둡니다.

```sql
CREATE ROLE wikijs LOGIN PASSWORD '<비밀번호>';
CREATE DATABASE wiki OWNER wikijs;
```

데이터베이스의 `pg_hba.conf`는 컨테이너가 접속하는 주소를 허용해야 합니다. Wiki.js는 시작할 때 데이터베이스 접속을 3초 간격으로 10번 시도하고, 그래도 실패하면 종료되어 재시작 정책에 따라 다시 시작됩니다.

### 같은 호스트의 PostgreSQL

`host.containers.internal`은 컨테이너에서 본 호스트 주소입니다. Podman은 자동으로 넣고, Compose는 `extra_hosts`의 `host-gateway`로 Docker에도 같은 이름을 넣습니다. 이 주소는 호스트의 루프백이 아닙니다. [`postgresql/`](../postgresql/README.md)처럼 `127.0.0.1:5432`에만 열린 데이터베이스에는 닿지 않습니다.

| 방법 | 설정 |
|---|---|
| Quadlet, `postgresql/` Quadlet | 기본값. `Network=postgres.network`로 `postgres-network`에 붙어 컨테이너 이름 `postgres`로 접속 |
| Quadlet, rootless | `Network=postgres.network`를 지우고 `Network=pasta:-T,5432` 주석을 풀고 `DB_HOST=127.0.0.1`로 바꿈. pasta가 컨테이너 안의 `127.0.0.1:5432`를 호스트 `127.0.0.1:5432`로 넘김 |
| Compose | `postgres` 프로필로 PostgreSQL을 함께 띄움 |
| 그 밖의 경우 | 데이터베이스를 컨테이너가 닿는 주소(호스트 LAN 주소, 브리지 주소)에도 열고 그 주소를 `DB_HOST`에 적음. 모든 인터페이스에 열지 않도록 방화벽과 `pg_hba.conf`로 제한 |

Quadlet의 `Network=postgres.network`는 `postgresql/postgresql.quadlets`를 먼저 설치해야 동작합니다. 설치하지 않은 상태로 두면 Quadlet이 `wikijs` 유닛을 만들지 못합니다.

## 실행

### Docker Compose

외부 PostgreSQL을 쓸 때:

```sh
cd wiki.js
cp example.env .env   # DB_HOST, DB_PASS를 채운다
docker compose config
docker compose up -d
docker compose logs -f wiki
```

PostgreSQL을 함께 띄울 때는 `.env`에 다음을 적습니다. `postgres` 서비스는 `DB_USER`, `DB_NAME`, `DB_PASS`로 데이터베이스를 처음 한 번 초기화합니다. 첫 기동 뒤에 이 값을 바꾸면 데이터베이스에는 반영되지 않습니다.

```sh
COMPOSE_PROFILES=postgres
DB_HOST=postgres
DB_PASS=<비밀번호>
```

```sh
docker compose config
docker compose up -d
```

`.env` 값이 `default.env`보다 우선합니다. `default.env`, `.env`는 Wiki.js에만 들어갑니다. `postgres` 서비스는 Compose가 `.env`에서 `DB_USER`, `DB_NAME`, `DB_PASS`를 읽어 채우며, 없으면 `default.env`와 같은 기본값을 씁니다. PostgreSQL 포트는 호스트에 공개하지 않습니다.

확인:

```sh
curl -fsS http://127.0.0.1:3001/healthz
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다. 기본값은 [`postgresql/`](../postgresql/README.md) Quadlet의 `postgres-network`에 붙습니다. 다른 데이터베이스를 쓰면 설치 전에 `wiki.js.quadlets`의 `Network=`, `DB_HOST`를 실제 값으로 바꿉니다. secret은 한 번만 만들면 재시작해도 유지됩니다.

```sh
cd wiki.js
printf '%s' '<비밀번호>' | podman secret create wikijs-db-password -
podman quadlet install wiki.js.quadlets
systemctl --user daemon-reload
systemctl --user start wikijs
journalctl --user -u wikijs -f
```

비밀번호를 바꾸려면 `podman secret rm wikijs-db-password` 후 다시 만들고 `wikijs`를 재시작합니다.

`podman quadlet install`은 이미 설치된 파일을 덮어쓰지 않습니다. `.quadlets`를 고친 뒤에는 `podman quadlet install --replace wiki.js.quadlets`, `systemctl --user daemon-reload`, `systemctl --user restart wikijs` 순서로 다시 적용합니다.

rootful로 실행할 때는 `sudo podman quadlet install wiki.js.quadlets` 후 `sudo systemctl daemon-reload`, `sudo systemctl start wikijs`를 사용합니다. `Network=pasta:-T,5432`는 rootless에서만 씁니다.

### podman kube play

실행 전에 `pod.yaml`의 ConfigMap `wikijs`에 호스트와 사용자를, Secret `wikijs-db`에 비밀번호를 적습니다. 비밀번호를 넣은 `pod.yaml`은 커밋하지 않습니다.

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

Pod 이름은 `wikijs`, 컨테이너 이름은 `wikijs-wiki`입니다. `podman kube down`은 PVC 볼륨을 지우지 않습니다. 데이터까지 지우려면 `podman volume rm wikijs-data`를 실행합니다.

Quadlet과 kube play는 같은 볼륨 `wikijs-data`를 씁니다. Compose 볼륨은 프로젝트 접두어가 붙어 `wikijs_wikijs-data`입니다. 프로젝트 이름은 디렉터리 이름 `wiki.js`에서 `.`을 뺀 `wikijs`입니다. 세 방식 모두 같은 호스트 포트를 쓰므로 동시에 실행하지 않습니다.

## 연동 서비스 네트워크

[`wikijs-gateway/`](../wikijs-gateway/README.md)처럼 Wiki.js GraphQL API(`/graphql`)를 부르는 서비스는 `127.0.0.1:3001`에 닿지 못합니다. 컨테이너 안의 `127.0.0.1`은 그 컨테이너 자신입니다. 대신 `wikijs-network`에 붙어 `http://wikijs:3000/graphql`로 접속합니다.

| 실행 방식 | 네트워크 | Wiki.js 주소 |
|---|---|---|
| Compose | 기본 네트워크 이름을 `wikijs-network`로 고정. 연동 서비스는 `external: true`로 붙음 | `wikijs` (컨테이너 이름), `wiki` (서비스 이름) |
| Quadlet | `wikijs.network` 유닛(`wikijs-network`). 연동 서비스는 `Network=wikijs.network` | `wikijs` |
| kube play | `podman network create wikijs-network` 후 `podman kube play --network wikijs-network pod.yaml` | `wikijs-wiki` (컨테이너 이름) |

## 리버스 프록시

`nginx/wiki.js.conf`와 `caddy/wiki.js.caddyfile`은 같은 호스트 이름과 업스트림을 가리킵니다.

| 호스트 이름 | 업스트림 | 용도 |
|---|---|---|
| `wiki.example.com` | `127.0.0.1:3001` | 웹 UI, GraphQL API |

호스트 이름과 인증서 경로를 실제 값으로 바꿉니다.

| 프록시 | 연결 방법 |
|---|---|
| Nginx | `nginx/wiki.js.conf`를 프록시의 `conf.d/`에 복사하고 `nginx -t` 후 다시 읽기 |
| Caddy | 프록시 Caddyfile에 `import /path/to/wiki.js.caddyfile`을 추가하고 `caddy validate --adapter caddyfile --config <Caddyfile>` 후 다시 읽기 |

두 파일은 같은 의미로 다음을 담습니다.

- 업로드 본문 제한은 64MB입니다. Wiki.js 기본 업로드 제한은 파일당 5MB, 한 번에 10개입니다. 관리 화면(**관리 > 업로드**)에서 제한을 늘리면 두 프록시를 함께 늘립니다.
- GraphQL 구독(`/graphql-subscriptions`)은 WebSocket을 씁니다. Nginx는 `Upgrade`, `Connection` 헤더를 넘기고, Caddy는 자동으로 처리합니다.
- TLS는 프록시에서 끝냅니다.

프록시를 쓰면 Wiki.js 관리 화면에서 다음을 바꿉니다.

- **관리 > 일반 > 사이트 URL**: `https://wiki.example.com`. 링크, 로그인 리다이렉트, 사이트맵에 쓰입니다.
- **관리 > 보안 > 프록시 신뢰**(`securityTrustProxy`): 켜야 `X-Forwarded-For`, `X-Forwarded-Proto`로 클라이언트 IP와 HTTPS를 인식합니다. 프록시를 거치지 않고 포트에 직접 닿을 수 있으면 켜지 않습니다.

## Git 저장소 SSH 키

SSH 키는 관리 화면 **관리 > 저장소 > Git**에서 인증 방식을 SSH로 둘 때만 필요합니다. 페이지를 Git 원격 저장소와 동기화하는 기능이며, 쓰지 않으면 키를 넣지 않습니다.

Wiki.js는 `~/.ssh`를 읽지 않습니다. 이미지의 실행 사용자는 `node`(홈 `/home/node`)이고, `/home/git/.ssh`는 Gitea 같은 Git 서버 이미지의 경로입니다. Git 모듈은 저장소에 `core.sshCommand`를 `ssh -i "<키 경로>" -o StrictHostKeyChecking=no`로 설정합니다. 키 경로만 맞으면 되고 `known_hosts`는 필요 없습니다. 키에는 암호가 없어야 합니다.

키를 넣는 방법은 **SSH Private Key Mode**에 따라 둘입니다.

| 모드 | 키 위치 | 이 구성에서 할 일 |
|---|---|---|
| `contents` | 관리 화면에 붙여 넣은 내용이 DB에 저장되고, 모듈이 시작할 때 `/wiki/data/secure/git-ssh.pem`에 씀 | 없음. 세 실행 방식 모두 그대로 동작 |
| `path` (기본값) | **SSH Private Key Path**에 적은 컨테이너 안 절대 경로 | 키 파일을 컨테이너에 넣음 (아래 표) |

| 실행 방식 | `path` 모드에서 키 넣기 |
|---|---|
| Compose | `compose.yaml`의 `./keys/git-ssh:/run/secrets/git-ssh:ro,Z` 주석을 풂. 키 파일은 `node`(1000)가 읽을 수 있어야 하고, 소유자가 1000이면 권한은 `0600`. rootless Podman에서는 호스트 사용자가 컨테이너 root가 되므로 `podman unshare chown 1000:1000 keys/git-ssh`로 맞춤 |
| Quadlet | `podman secret create wikijs-git-ssh ~/.ssh/<키 파일>` 후 `wiki.js.quadlets`의 `Secret=wikijs-git-ssh,type=mount,...` 주석을 풂. 소유자 1000, 권한 `0400`으로 `/run/secrets/git-ssh`에 마운트됨 |
| kube play | `contents` 모드를 씀 |

경로는 관리 화면에 `/run/secrets/git-ssh`로 적습니다. `keys/`는 커밋하지 않습니다.

## 소유자와 SELinux

| 컨테이너 | 실행 사용자 | 쓰는 경로 | 처리 |
|---|---|---|---|
| Wiki.js | `node` (`1000`) | `/wiki/data/content` (이미지에서 `node:node`) | 이름 있는 볼륨이 처음 쓸 때 이미지 소유자를 복사 |
| PostgreSQL (`postgres` 프로필) | `postgres` (`999`) | `/var/lib/postgresql` | 엔트리포인트가 root로 시작해 소유권을 맞춤 |

- 이름 있는 볼륨 `wikijs-data`는 `/wiki/data/content`에 마운트합니다. 이미지가 `VOLUME`으로 선언한 경로는 이것 하나입니다. `/wiki/data`에 마운트하면 `/wiki/data/content`가 익명 볼륨으로 따로 잡혀 이름 있는 볼륨에 들어가지 않습니다.
- `/wiki/data`의 나머지(`dataPath`)는 영구 저장소가 아닙니다. `cache/`는 데이터베이스에 있는 첨부 파일의 캐시, `uploads/`는 업로드 임시 파일이고, Wiki.js가 비우거나 다시 만듭니다. `sideload/`는 오프라인 언어 파일을 넣을 때만 씁니다.
- 페이지와 첨부 파일 원본은 데이터베이스에 있습니다. 파일로도 남기려면 관리 화면 **관리 > 저장소 > 로컬 파일 시스템**을 켜고 경로를 `/wiki/data/content`로 지정합니다. 이 저장소는 기본 경로가 없습니다. **Git** 저장소의 기본 로컬 경로(`./data/repo`)는 볼륨 밖이라 컨테이너를 다시 만들면 원격에서 다시 받습니다. 남기려면 `/wiki/data/content/repo`로 바꿉니다.
- 볼륨에 `U`를 붙이지 않습니다. `U`는 기동할 때마다 볼륨 전체를 재귀적으로 `chown`합니다.
- 볼륨 소유권이 어긋나 Wiki.js가 `/wiki/data/content`에 쓰지 못하면 한 번만 맞춥니다. rootless Podman은 `podman unshare chown -R 1000:1000 "$(podman volume inspect -f '{{.Mountpoint}}' wikijs-data)"`입니다.
- SELinux 호스트에서는 Quadlet 마운트의 `:Z`가 데이터에 컨테이너 전용 레이블을 붙입니다. SELinux가 꺼진 호스트에서는 무시됩니다. Compose 이름 있는 볼륨과 kube play PVC는 엔진이 레이블을 관리합니다.

## 주의 사항

- 페이지, 첨부 파일, 사용자, 설정은 데이터베이스에 있습니다. 백업의 기준은 데이터베이스입니다. 로컬 파일 시스템 저장소를 켰다면 `wikijs-data` 볼륨도 함께 백업합니다.
- 상태 확인은 `http://localhost:3000/healthz`를 이미지에 있는 `curl`로 호출합니다. 데이터베이스 커넥션 풀이 비어 있으면 `503`을 돌려줍니다. 첫 기동 유예는 60초입니다. Quadlet은 상태 확인이 실패하면 컨테이너를 종료해 다시 시작합니다. Compose는 상태 확인 실패만으로 다시 시작하지 않습니다.
- `NoNewPrivileges`와 `NET_RAW`, `NET_ADMIN` 제거를 적용합니다.
- 실서버에서 태그를 지정할 때는 `2` 또는 `2.5.<패치>`로 둡니다. 2.x에서 3.x로는 같은 데이터베이스로 올려갈 수 없습니다. 갱신 전에는 데이터베이스와 볼륨을 백업합니다.
- `postgres` 프로필의 PostgreSQL은 `latest`(18)이므로 `/var/lib/postgresql`을 마운트합니다. 실서버에서 17 이하로 지정하면 마운트 경로를 `/var/lib/postgresql/data`로 바꿉니다.

## 참고 자료

- [Wiki.js Docker 설치](https://docs.requarks.io/install/docker)
- [Wiki.js 설정](https://docs.requarks.io/install/config)
- [Wiki.js 2.5 Dockerfile](https://github.com/requarks/wiki/blob/v2.5.314/dev/build/Dockerfile)
- [이미지 내장 config.yml](https://github.com/requarks/wiki/blob/v2.5.314/dev/build/config.yml)
- [컨테이너 이미지](https://github.com/requarks/wiki/pkgs/container/wiki)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
- [pasta](https://passt.top/builds/latest/web/passt.1.html)
