# gitea

[Gitea](https://about.gitea.com/) Git 서비스를 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다. 세 방식 모두 rootless 이미지(`docker.gitea.com/gitea:latest-rootless`) 컨테이너 하나와 SQLite를 씁니다. 컨테이너는 처음부터 UID 1000(`git`)으로 실행되며, OpenSSH 대신 Gitea 내장 SSH 서버를 씁니다.

웹 UI는 `127.0.0.1:3000`에서만 열리고, Git SSH는 `2222`로 모든 인터페이스에 열립니다. 다른 호스트에서 웹 UI에 접속하려면 [리버스 프록시](#리버스-프록시)를 앞에 둡니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `example.env` | `.env`에 적을 키와 예시 |
| `gitea.quadlets` | Podman Quadlet (볼륨, 컨테이너) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap |
| `nginx/gitea.conf` | Nginx `server` 블록 |
| `caddy/gitea.caddyfile` | Caddy 사이트 블록 |
| `../gitea-runner/` | Gitea Actions runner. 사용법은 [gitea-runner/README.md](../gitea-runner/README.md) |

## 설정 방식

서버 설정은 `GITEA__섹션__키` 환경 변수로 줍니다. 컨테이너가 시작할 때마다 이 값이 `/etc/gitea/app.ini`에 덮어써집니다. `app.ini`가 없을 때만 이미지 템플릿으로 새로 만들고, 있으면 그 파일을 그대로 씁니다. 설치 마법사나 관리 화면에서 같은 항목을 바꿔도 재시작하면 환경 변수 값으로 돌아갑니다. 값을 바꾸면 `default.env`, `gitea.quadlets`의 `Environment=`, `pod.yaml` ConfigMap `gitea-default`를 함께 수정합니다.

| 항목 | 기본값 | 비고 |
|---|---|---|
| `GITEA__server__ROOT_URL` | `http://localhost:3000/` | 실제 접속 주소로 바꿉니다 |
| `GITEA__server__SSH_DOMAIN` | `localhost` | SSH 클론 URL의 호스트 |
| `GITEA__server__SSH_PORT` | `2222` | 호스트에 공개한 SSH 포트 |
| `GITEA__server__SSH_LISTEN_PORT` | `2222` | 내장 SSH 서버가 컨테이너 안에서 여는 포트. UID 1000은 1024 미만 포트를 열 수 없습니다 |
| `GITEA__database__DB_TYPE` | `sqlite3` | `/var/lib/gitea/data/gitea.db` |
| `GITEA__service__DISABLE_REGISTRATION` | `true` | 관리자가 계정을 만듭니다 |
| `GITEA__service__REQUIRE_SIGNIN_VIEW` | `true` | 로그인해야 저장소를 봅니다 |
| `GITEA__actions__ENABLED` | `true` | Actions 사용 |

`ROOT_URL`은 사용자가 접속하는 주소이면서 Actions job 컨테이너가 저장소를 checkout하는 주소입니다. 운영에서는 `localhost`, `127.0.0.1`을 쓰지 않고 `.env`에 프록시 주소(예: `https://gitea.example.com/`)를 적습니다. runner의 `GITEA_INSTANCE_URL`도 같은 주소로 맞춥니다.

### 설치 마법사

`INSTALL_LOCK`은 환경 변수로 주지 않습니다. 처음 접속하면 설치 마법사가 열리고, 위 값이 미리 채워져 있습니다. 마법사에서 관리자 계정을 만들고 마치면 `SECRET_KEY`, `INTERNAL_TOKEN`과 `INSTALL_LOCK=true`가 `app.ini`에 저장됩니다. 마법사는 처음 접속한 사람이 진행할 수 있으므로 컨테이너를 띄운 직후 바로 마칩니다.

`GITEA__security__INSTALL_LOCK=false`를 환경 변수에 두면 재시작할 때마다 마법사가 다시 열립니다. 마법사 없이 시작하려면 `true`로 두고 관리자를 명령으로 만듭니다.

```sh
docker exec gitea gitea -c /etc/gitea/app.ini admin user create --admin \
  --username admin --email admin@example.com --random-password
```

## 실행

### Docker Compose

데이터는 `./.data/data`(`/var/lib/gitea`)와 `./.data/config`(`/etc/gitea`)에 저장됩니다. 프로젝트 이름은 디렉터리 이름(`gitea`)을 따릅니다.

컨테이너 UID 1000이 바인드 마운트에 쓸 수 있어야 합니다. 디렉터리가 없으면 엔진이 root 소유로 만들어 `is not writable`로 기동에 실패합니다. 처음 한 번 디렉터리를 만들고 소유자를 바꿉니다. 아래 명령은 컨테이너 안에서 `chown`하므로 rootful Docker, rootless Docker, rootless Podman 모두에서 UID 매핑이 맞습니다(Podman이면 `docker`를 `podman`으로 바꿉니다).

```sh
cd gitea
mkdir -p .data/data .data/config
docker run --rm -v "$(pwd)/.data:/d:Z" docker.io/library/alpine:latest chown -R 1000:1000 /d
docker compose config
docker compose up -d
curl -fsS http://127.0.0.1:3000/api/healthz
```

주소를 바꾸려면 `example.env`를 참고해 필요한 키만 `.env`에 적습니다. `.env` 값이 `default.env`보다 우선합니다.

### Podman Quadlet

Podman 5.6 이상이 필요합니다. Pod 없이 컨테이너 하나로 실행하며 데이터는 `gitea-data`(`/var/lib/gitea`), 설정은 `gitea-config`(`/etc/gitea`) 볼륨에 둡니다. 빈 named volume은 처음 마운트할 때 이미지 디렉터리의 소유자(UID 1000)를 이어받으므로 따로 `chown`하지 않습니다. 설치 전에 `gitea.quadlets`의 `ROOT_URL`, `SSH_DOMAIN`을 실제 값으로 바꿉니다.

```sh
cd gitea
podman quadlet install gitea.quadlets
systemctl --user daemon-reload
systemctl --user start gitea
```

`podman quadlet install`은 이미 설치된 파일을 덮어쓰지 않습니다. `.quadlets`를 고친 뒤에는 `podman quadlet install --replace gitea.quadlets`, `systemctl --user daemon-reload`, `systemctl --user restart gitea` 순서로 다시 적용합니다.

이전 구성(Pod `gitea`, 컨테이너 `gitea-app`, 또는 표준 이미지와 볼륨 `gitea-vol`)을 설치했다면 먼저 지웁니다. 남은 유닛은 `podman quadlet list`로 확인합니다. `gitea-vol`의 데이터는 새 볼륨으로 이어지지 않으므로 [표준 이미지에서 옮기기](#표준-이미지에서-옮기기)를 따라 옮깁니다.

```sh
systemctl --user stop gitea
podman quadlet rm gitea.pod gitea-app.container
podman quadlet install gitea.quadlets
systemctl --user daemon-reload
systemctl --user start gitea
```

### podman kube play

PVC `gitea-data`, `gitea-config`가 같은 이름의 Podman 볼륨으로 만들어집니다. Quadlet과 볼륨 이름이 같으므로 두 방식을 함께 쓰지 않습니다. 실행 전에 ConfigMap `gitea-default`의 주소를 바꿉니다.

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

컨테이너 이름은 `gitea-gitea`입니다. `podman kube down`은 볼륨을 지우지 않습니다.

실행 후 `http://127.0.0.1:3000/`에서 설치 마법사를 진행합니다.

## 리버스 프록시

`nginx/gitea.conf`와 `caddy/gitea.caddyfile`은 `gitea.example.com`을 `127.0.0.1:3000`으로 넘깁니다. 호스트 이름과 인증서 경로를 실제 값으로 바꿔 씁니다. 웹 UI는 루트 경로(`/`)에서 열고, `ROOT_URL`도 같은 주소로 둡니다.

| 프록시 | 연결 방법 |
|---|---|
| Nginx | `nginx/gitea.conf`를 프록시의 `conf.d/`에 복사하고 `nginx -t` 후 다시 읽기 |
| Caddy | 프록시 Caddyfile에 `import /path/to/gitea.caddyfile`을 추가하고 `caddy validate --adapter caddyfile --config <Caddyfile>` 후 다시 읽기 |

두 파일은 같은 의미로 다음을 담습니다.

- WebSocket: 28부터 알림 수, 스톱워치, 로그아웃 이벤트가 SSE(`/user/events`) 대신 WebSocket(`/-/ws`)을 씁니다. Nginx는 `Upgrade`, `Connection` 헤더를 넘기고, Caddy는 기본으로 넘깁니다. 넘기지 않으면 폴링으로 동작합니다.
- 업로드 크기: HTTP push, LFS, 패키지 업로드를 위해 요청 본문을 512MB까지 허용합니다.
- 타임아웃: 큰 저장소 clone, push를 위해 Nginx는 읽기/쓰기 타임아웃을 300초로 늘립니다. Caddy는 기본 타임아웃이 없습니다.

Git SSH는 프록시를 거치지 않고 호스트 `2222`로 바로 접속합니다. Gitea는 `127.0.0.1`, `::1`에서 온 `X-Forwarded-For`만 믿습니다. 프록시가 다른 주소에서 접속하면 `GITEA__security__REVERSE_PROXY_TRUSTED_PROXIES`에 그 주소를 적습니다.

## Gitea 28 변경 사항

이미지는 `docker.gitea.com/gitea:latest-rootless`이며 2026-10 기준 28.2.0을 가리킵니다. 28.0부터 버전에서 `1.` 접두어가 빠졌습니다(1.28이 아니라 28). 이 구성은 28에 맞춰 다음을 반영합니다.

- `[server] DOMAIN`은 더 이상 읽지 않습니다. 도메인과 기본 SSH 도메인은 `ROOT_URL`에서 얻으므로 `DOMAIN` 키를 두지 않습니다.
- 셀프 회원가입이 기본 차단으로 바뀌었습니다. 허용하려면 `GITEA__service__DISABLE_REGISTRATION=false`를 명시합니다.
- 완료된 Actions run은 400일 뒤 job, 로그, 아티팩트와 함께 지워집니다. 영구 보관하려면 `GITEA__actions__RUN_RETENTION_DAYS=0`을 둡니다.
- `[ui.notification] EVENT_SOURCE_UPDATE_TIME`은 없어졌습니다. Gitea 프로세스가 여럿일 때만 `[websocket] PUBSUB_TYPE=redis`가 필요하고, 컨테이너 하나에는 필요 없습니다.
- 마이그레이션, 미러의 외부 접근은 내부 egress 프록시를 거칩니다. `[migrations] ALLOWED_DOMAINS`, `BLOCKED_DOMAINS`, `ALLOW_LOCALNETWORKS`는 `ALLOWED_HOST_LIST`, `BLOCKED_HOST_LIST`로 바뀌었고, 목록만 허용하려면 `EGRESS_MODE=strict`를 둡니다. `BLOCKED_HOST_LIST`에 IP 와일드카드(`192.168.1.*`)나 `*` 같은 잘못된 항목이 있으면 시작하지 않습니다.
- Actions workflow 평가가 엄격해졌습니다. job의 `if:`는 matrix 전개 전에 평가되고, matrix `fail-fast`가 적용됩니다.

1.x 데이터로 28을 띄우면 DB가 마이그레이션되고 1.x로 되돌릴 수 없습니다. 올리기 전에 두 볼륨을 백업합니다.

## 표준 이미지에서 옮기기

표준 이미지(`latest`)는 모든 데이터를 `/data` 하나에 두고, rootless 이미지는 `/var/lib/gitea`와 `/etc/gitea`로 나눕니다. 이미지 태그만 바꾸면 새 경로가 비어 있어 설치 마법사가 다시 열리므로 데이터를 옮깁니다.

| 표준 이미지 | rootless 이미지 |
|---|---|
| `/data/git/repositories`, `/data/git/lfs` | `/var/lib/gitea/git/repositories`, `/var/lib/gitea/git/lfs` |
| `/data/gitea/`(DB, 첨부, 아바타, 패키지 등) | `/var/lib/gitea/data/` |
| `/data/gitea/conf/app.ini` | `/etc/gitea/app.ini` |
| `/data/ssh/`(OpenSSH 호스트 키) | 쓰지 않습니다. 내장 SSH 서버가 `data/ssh/gitea.rsa`를 새로 만듭니다 |

기존 `app.ini`에는 `/data/...` 절대 경로가 적혀 있으므로 옮기면서 함께 바꿉니다. Quadlet 볼륨 기준 예시입니다. 먼저 Gitea를 멈추고 `gitea-vol`을 백업합니다.

```sh
systemctl --user stop gitea
podman volume create gitea-data
podman volume create gitea-config
podman run --rm \
  -v gitea-vol:/old:ro \
  -v gitea-data:/new/data \
  -v gitea-config:/new/config \
  docker.io/library/alpine:latest sh -c '
    mkdir -p /new/data/git /new/data/data
    cp -a /old/git/. /new/data/git/
    cp -a /old/gitea/. /new/data/data/
    rm -rf /new/data/data/conf
    sed -e "s#= /data/gitea#= /var/lib/gitea/data#" \
        -e "s#= /data/git#= /var/lib/gitea/git#" \
        /old/gitea/conf/app.ini > /new/config/app.ini
    chown -R 1000:1000 /new'
systemctl --user start gitea
```

옮긴 뒤 `podman exec gitea grep -n /data /etc/gitea/app.ini`로 남은 옛 경로가 없는지 확인합니다. Compose는 `./.data/git`, `./.data/gitea`를 `./.data/data/git`, `./.data/data/data`로 옮기고 같은 `sed`로 `./.data/config/app.ini`를 만든 뒤 위 `chown`을 실행합니다.

SSH 호스트 키가 바뀌므로 클라이언트에서 `ssh-keygen -R "[<SSH_DOMAIN>]:2222"`로 `known_hosts`의 옛 키를 지웁니다. 사용자 SSH 공개 키는 DB에 있어 그대로 이어집니다.

## 주의 사항

- 저장소, SQLite DB, LFS, SSH 호스트 키는 `/var/lib/gitea`(Compose `./.data/data`, Quadlet, kube play `gitea-data`), `app.ini`는 `/etc/gitea`(Compose `./.data/config`, Quadlet, kube play `gitea-config`)에 저장됩니다. 지우면 모든 저장소가 함께 사라집니다.
- 이미지가 두 경로를 `VOLUME`으로 선언하므로 마운트를 빠뜨리면 익명 볼륨에 데이터가 쌓입니다. Quadlet은 컨테이너를 `--rm`으로 실행하므로 컨테이너를 다시 만들면 그 데이터가 사라집니다.
- `app.ini`의 `SECRET_KEY`는 2FA 시크릿 같은 DB 내 암호화 데이터에 쓰이므로 데이터를 옮길 때 `app.ini`도 함께 옮깁니다.
- SELinux 호스트에서는 바인드 마운트에 `:Z`를 붙입니다. Podman named volume은 자동으로 레이블이 붙지만, 데이터를 `cp -a` 등으로 레이블째 복사했거나 Quadlet `Volume=`을 호스트 경로로 바꿨다면 `:Z`를 붙입니다.
- 이미지는 root를 거치지 않고 UID 1000으로 바로 실행하므로 `USER_UID`, `USER_GID`를 읽지 않고 마운트 소유자를 바꾸지도 않습니다. 바인드 마운트는 [Docker Compose](#docker-compose)처럼 미리 소유자를 맞춥니다. rootless Podman에서 컨테이너 UID 1000은 호스트의 subuid로 매핑되므로 호스트에서 `chown 1000`을 하면 맞지 않습니다.
- 웹 포트는 `127.0.0.1`에만 엽니다. 프록시가 컨테이너로 실행되거나 다른 호스트에 있다면 `127.0.0.1:`을 빼거나 프록시를 같은 네트워크에 붙입니다. 포트를 바꾸면 Compose `ports`, Quadlet `PublishPort`, `pod.yaml`의 `hostPort`, 프록시 업스트림을 함께 수정합니다.
- 같은 호스트의 `adguard`도 `3000`을 씁니다. 함께 실행하려면 한쪽 호스트 포트를 바꿉니다.
- 시간대는 `/etc/localtime` 마운트 대신 `TZ`로 지정합니다.
- 재시작 정책은 Compose `always`, Pod `Always`, Quadlet `Restart=on-failure`입니다. Quadlet은 상태 확인이 실패하면 컨테이너를 종료해 다시 시작합니다.
- 상태 확인은 `http://localhost:3000/api/healthz`를 이미지에 들어 있는 `curl`로 요청합니다.
- `latest-rootless`는 다시 받을 때마다 버전이 바뀔 수 있습니다. 버전을 고정하려면 세 파일의 태그를 같은 버전(예: `28.2.0-rootless`)으로 바꿉니다. `-rootless`를 빼면 표준 이미지가 되어 볼륨 경로와 SSH 포트가 맞지 않습니다. 올리기 전에는 데이터를 백업하고 릴리스 노트의 breaking change를 확인합니다.

## 참고 자료

- [Gitea 28.0.0 릴리스](https://blog.gitea.com/release-of-28.0.0/)
- [Gitea Docker 설치](https://docs.gitea.com/installation/install-with-docker)
- [환경 변수로 app.ini 구성](https://docs.gitea.com/installation/install-with-docker#managing-deployments-with-environment-variables)
- [설정 항목](https://docs.gitea.com/administration/config-cheat-sheet)
- [리버스 프록시](https://docs.gitea.com/administration/reverse-proxies)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
