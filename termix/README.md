# termix

[Termix](https://docs.termix.site/) SSH/RDP/VNC 웹 관리 도구를 로컬에서 실행하기 위한 구성입니다. Termix가 RDP, VNC, Telnet을 직접 처리하므로 guacd 없이 컨테이너 하나만 실행합니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

웹 UI는 `127.0.0.1:8080`에서만 열리며, `http://127.0.0.1:8080/`로 접속합니다. 다른 호스트에서 접속하려면 [리버스 프록시](#리버스-프록시)를 앞에 둡니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env` | Compose 기본 환경 변수 |
| `example.env` | `.env`에 적을 선택 키 예시 |
| `termix.quadlets` | Podman Quadlet (컨테이너) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap |
| `nginx/termix.conf` | Nginx `server` 블록 |
| `caddy/termix.caddyfile` | Caddy 사이트 블록 |

## 관리자 계정

별도 관리자 비밀번호 설정은 없으며, 처음 가입한 계정이 관리자가 됩니다. 서비스를 시작한 직후 바로 계정을 만들고, 필요하면 관리자 설정에서 신규 가입을 막습니다.

JWT 서명 키, 데이터베이스 암호화 키 같은 비밀값은 첫 실행 때 자동으로 생성되어 `/app/data`에 저장됩니다. 데이터를 잃으면 저장된 호스트 자격 증명도 복호화할 수 없으므로 데이터 전체를 백업합니다.

## 실행

### Docker Compose

데이터는 이름 있는 볼륨 `termix-vol`에 저장합니다. 컨테이너는 root로 시작해 `/app/data`를 `node`(`PUID:PGID`, 기본 1000:1000) 소유로 바꾼 뒤 `node`로 실행됩니다.

```sh
cd termix
docker compose config
docker compose up -d
```

기본값을 바꾸려면 `example.env`를 참고해 `.env`를 만들고 필요한 변수만 적습니다. `.env` 값이 `default.env`보다 우선합니다.

확인:

```sh
docker compose ps
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다.

```sh
podman quadlet install termix.quadlets
systemctl --user daemon-reload
systemctl --user start termix
```

- 데이터는 `~/.local/share/termix`에 바인드 마운트합니다. 디렉터리가 없으면 `ExecStartPre`가 만듭니다.
- `UserNS=keep-id:uid=1000,gid=1000`으로 호스트 사용자를 컨테이너의 `node`(1000:1000)에 매핑합니다. 컨테이너가 root로 시작하지 않으므로 엔트리포인트의 `chown`/`gosu` 단계를 건너뛰고 바로 `node`로 실행됩니다.
- 마운트의 `U`는 디렉터리 소유자를 컨테이너 사용자(`node`)에 맞춥니다. `keep-id`로 `node`가 호스트 사용자에 매핑되므로 호스트에서 보면 파일 소유자는 현재 사용자입니다. 백업할 때 `podman unshare`가 필요 없습니다.
- SELinux 호스트에서는 `:Z`로 이 컨테이너 전용 레이블을 붙입니다. 다른 컨테이너와 같은 디렉터리를 공유하면 `:z`로 바꿉니다. SELinux가 꺼진 호스트에서는 무시됩니다.
- `keep-id`를 처음 적용할 때 이미지 레이어 소유권을 다시 맞추느라 시작이 느릴 수 있어 `TimeoutStartSec=900`을 둡니다.
- `AutoUpdate=registry`로 설정되어 있어 `podman auto-update`로 이미지를 갱신할 수 있습니다.

이전 Pod 구성(`termix-vol` 볼륨)에서 옮길 때는 데이터를 복사한 뒤 기존 유닛을 지웁니다.

```sh
systemctl --user stop termix
mkdir -p ~/.local/share/termix
# 컨테이너 root(=호스트 사용자)로 복사해 새 파일 소유자를 현재 사용자로 맞춘다
podman run --rm -v termix-vol:/from:ro -v ~/.local/share/termix:/to:Z \
  docker.io/library/alpine cp -R /from/. /to/
```

옛 Pod 구성의 `termix-guacd`, `termix-app` 유닛은 `podman quadlet list`로 확인한 뒤 `podman quadlet rm`으로 지웁니다.

### podman kube play

PVC `termix-vol`이 같은 이름의 Podman 볼륨으로 만들어집니다. 이전 Pod 구성과 볼륨 이름이 같아 기존 데이터를 그대로 씁니다. 소유권은 Compose처럼 엔트리포인트가 맞춥니다.

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

## 리버스 프록시

`nginx/termix.conf`와 `caddy/termix.caddyfile`은 `termix.example.com`을 `127.0.0.1:8080`으로 넘깁니다. 호스트 이름과 인증서 경로를 실제 값으로 바꿔 씁니다. 웹 UI는 루트 경로(`/`)에서 엽니다.

| 프록시 | 연결 방법 |
|---|---|
| Nginx | `nginx/termix.conf`를 프록시의 `conf.d/`에 복사하고 `nginx -t` 후 다시 읽기 |
| Caddy | 프록시 Caddyfile에 `import /path/to/termix.caddyfile`을 추가하고 `caddy validate --adapter caddyfile --config <Caddyfile>` 후 다시 읽기 |

두 파일은 Termix가 요구하는 세 가지를 같은 의미로 담습니다.

- WebSocket: 터미널, 원격 데스크톱, 실시간 갱신이 사용합니다. Nginx는 `Upgrade`/`Connection` 헤더를 넘기고, Caddy는 기본으로 넘깁니다.
- 긴 타임아웃: 유휴 터미널이 끊기지 않게 Nginx는 읽기/쓰기 타임아웃을 하루로 둡니다. Caddy는 기본 타임아웃이 없고, 설정을 다시 읽을 때 열린 세션을 5분 동안 유지합니다(`stream_close_delay`).
- 업로드 크기: 파일 관리자가 큰 파일을 보내므로 Nginx는 `client_max_body_size 0`으로 제한을 풉니다. Caddy는 기본 제한이 없습니다.

Termix는 `X-Forwarded-For`를 사설 대역(127.0.0.1, 10/8, 172.16/12, 192.168/16)에서 온 경우에만 믿습니다. 프록시 주소가 이 범위 밖이거나 범위를 좁히려면 `.env`에 `TRUSTED_PROXIES`를 적습니다. rootless Podman 포트 포워딩이 원본 IP를 보존하지 않으면 감사 로그와 요청 제한에 프록시 대신 내부 주소가 남습니다.

## 외부 guacd (선택)

RD Gateway처럼 내장 엔진이 지원하지 않는 기능이 필요할 때만 guacd를 따로 실행합니다. `REMOTE_DESKTOP_ENGINE=guacd`와 `GUACD_HOST`를 지정하고, guacd 포트(4822)는 인증이 없으므로 호스트에 공개하지 않습니다. 자세한 내용은 [External guacd](https://docs.termix.site/plugins/remote-desktop#external-guacd-optional)를 참고합니다.

## 주의 사항

- 데이터(SQLite DB, 암호화 키, 플러그인, 업로드, SSL 인증서, 세션 녹화, RDP 드라이브)는 모두 `/app/data`에 저장됩니다. Compose와 kube play는 볼륨 `termix-vol`, Quadlet은 `~/.local/share/termix`를 씁니다.
- `PORT`를 바꾸면 컨테이너 내부 포트가 바뀌므로 Compose `ports`, Quadlet `PublishPort`, `pod.yaml`의 `containerPort`/`hostPort`, 프록시 업스트림도 함께 수정합니다.
- 상태 확인은 내부 백엔드의 `http://localhost:30001/health` 엔드포인트를 사용합니다. 이 포트는 공개하지 않습니다.
- 같은 호스트의 `wiremock`도 `127.0.0.1:8080`을 사용합니다. 함께 실행하려면 한쪽 호스트 포트를 바꿉니다.
- 재시작 정책은 Compose `unless-stopped`, Pod `Always`, Quadlet `Restart=on-failure`입니다. Quadlet은 상태 확인이 실패하면 컨테이너를 종료해 다시 시작합니다.
- 이미지는 `ghcr.io/termix-ssh/termix:latest`를 씁니다(`docker.io/termixssh/termix`와 같은 이미지). 이전 경로 `ghcr.io/lukegus/termix`는 쓰지 않습니다. 재현성이 필요하면 세 파일의 태그를 같은 버전(예: `:26.10.2`)으로 고정합니다.

## 참고 자료

- [Termix Docker 설치](https://docs.termix.site/install/server/docker)
- [Termix 리버스 프록시](https://docs.termix.site/configure/reverse-proxy)
- [Termix 환경 변수](https://docs.termix.site/configure/environment-variables)
- [Termix upstream compose](https://github.com/Termix-SSH/Termix/blob/main/docker/docker-compose.yml)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
