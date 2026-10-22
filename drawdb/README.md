# drawdb

[drawDB](https://github.com/drawdb-io/drawdb) 데이터베이스 ERD 편집기를 로컬에서 실행하기 위한 구성입니다. 공식 이미지 하나를 권장합니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

웹 UI는 `127.0.0.1:5173`에서만 열리며, 에디터는 `http://127.0.0.1:5173/editor`입니다. 이전 `docker-compose.yml`은 비공식 이미지 `avmesquita/drawdb`를 모든 인터페이스의 `5173`에 공개했습니다. 다른 호스트에서 접속하려면 [리버스 프록시](#리버스-프록시)를 앞에 둡니다.

이미지는 `ghcr.io/drawdb-io/drawdb:latest`입니다. 이 구성은 기동할 때 `VITE_BACKEND_URL`을 `/config.js`에 넣는 이미지(v1.8.2부터)를 기준으로 합니다. 그 전 태그는 환경 변수를 빌드 시점에만 읽습니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `example.env` | `.env`에 적을 키와 예시 |
| `drawdb.quadlets` | Podman Quadlet (컨테이너) |
| `pod.yaml` | `podman kube play`용 Pod, ConfigMap |
| `nginx/drawdb.conf` | Nginx `server` 블록 |
| `caddy/drawdb.caddyfile` | Caddy 사이트 블록 |

## 데이터

컨테이너는 정적 파일만 제공합니다. 다이어그램은 브라우저 IndexedDB에 남습니다. 다른 브라우저로 옮기거나 저장 공간을 지우면 사라지므로, 에디터에서 JSON으로 내보내 둡니다.

공유와 버그 리포트 메일은 별도 서버([drawdb-server](https://github.com/drawdb-io/drawdb-server))가 필요합니다. 이 구성에는 넣지 않습니다. 브라우저가 `VITE_BACKEND_URL`로 직접 호출하고, drawDB 컨테이너는 그 주소에 접속하지 않습니다. 값을 바꾸면 `default.env`(또는 `.env`), `drawdb.quadlets`의 `Environment=`, `pod.yaml` ConfigMap `drawdb-default`를 함께 수정한 뒤 컨테이너를 다시 시작합니다. 주소는 `/config.js`의 자바스크립트 문자열에 그대로 들어가므로 따옴표, 역슬래시, `$`를 넣지 않습니다. 비우면 앱 기본값 `http://localhost:5000`을 씁니다. `VITE_GIST_BACKEND_URL`을 비우면 gist 요청도 `VITE_BACKEND_URL`을 따릅니다.

## 실행

### Docker Compose

프로젝트 이름은 디렉터리 이름(`drawdb`)을 따릅니다.

```sh
cd drawdb
docker compose config
docker compose up -d
```

공유 서버 주소는 `example.env`를 참고해 `.env`에 적습니다. `.env` 값이 `default.env`보다 우선합니다.

확인:

```sh
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5173/
curl -fsS http://127.0.0.1:5173/config.js
```

`/config.js`에 `window.__DRAWDB_CONFIG__`가 있고 `Cache-Control: no-store`이면 기동 시 환경 변수가 반영된 것입니다.

### Podman Quadlet

Podman 5.6 이상이 필요합니다. 컨테이너 하나만 만듭니다. 데이터 볼륨은 없습니다.

```sh
cd drawdb
podman quadlet install drawdb.quadlets
systemctl --user daemon-reload
systemctl --user start drawdb
```

컨테이너는 `AutoUpdate=registry`로 설정되어 있어 `podman auto-update`로 이미지를 갱신할 수 있습니다.

### podman kube play

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

## 리버스 프록시

`nginx/drawdb.conf`와 `caddy/drawdb.caddyfile`은 같은 호스트 이름(`drawdb.example.com`)과 업스트림(`127.0.0.1:5173`)을 가리킵니다. 호스트 이름과 인증서 경로를 바꿔 사용합니다. 웹 UI는 루트 경로(`/`)와 에디터(`/editor`)에서 엽니다. 호스트 포트를 바꾸면 두 파일의 업스트림도 함께 고칩니다.

| 프록시 | 연결 방법 |
|---|---|
| Nginx | `nginx/drawdb.conf`를 프록시의 `conf.d/`에 복사하고 `nginx -t` 후 다시 읽기 |
| Caddy | 프록시 Caddyfile에 `import /path/to/drawdb.caddyfile`을 추가하고 `caddy validate --adapter caddyfile --config <Caddyfile>` 후 다시 읽기 |

공유를 쓰려면 `VITE_BACKEND_URL`을 브라우저가 도달하는 주소(프록시 뒤라면 `https://`)로 맞춥니다. 그 호출은 drawDB 업스트림을 거치지 않습니다.

## 소유자와 SELinux

| 항목 | 내용 |
|---|---|
| 실행 사용자 | nginx 마스터는 root. 워커는 공식 nginx 이미지가 만드는 `nginx` 사용자(uid/gid 101) |
| 데이터 경로 | 없음. 다이어그램은 브라우저에 있다 |
| 기동 시 쓰기 | 엔트리포인트가 이미지 레이어의 `/etc/nginx/conf.d/default.conf`를 만든다 |

- 호스트 경로를 마운트하지 않습니다. SELinux `:Z`와 소유자 변경(`chown`, Quadlet `U`)은 이 구성에 필요 없습니다. SELinux가 꺼진 호스트에서도 추가 작업이 없습니다.
- 엔트리포인트는 root로 `default.conf`를 쓴 뒤 워커만 `nginx`로 내립니다. 마운트에 `U`를 붙이면 기동마다 대상 전체를 재귀적으로 `chown`합니다. 정적 파일 경로에 붙일 이유가 없습니다.
- 읽기 전용 루트(`read_only: true`, Quadlet `ReadOnly=true`)를 켜면 `default.conf`를 쓰지 못해 `VITE_BACKEND_URL`이 `/config.js`에 들어가지 않습니다.
- `/usr/share/nginx/html`에 이름 있는 볼륨이나 호스트 디렉터리를 올리면 이미지 안의 앱 파일이 가려집니다. 이전 `avmesquita/drawdb`의 `drawdb:/var/www/html`은 공식 이미지가 쓰지 않습니다. 남아 있으면 `docker volume rm drawdb`로 지웁니다.
- 호스트 디렉터리를 마운트하도록 직접 바꿀 때만 SELinux 호스트에서 `:Z`를 붙입니다. SELinux가 꺼진 호스트에서는 `:Z`가 무시됩니다. 그때도 `U`는 붙이지 않습니다. 디렉터리를 nginx 워커가 읽게 하려면 rootless Podman에서 `podman unshare chown -R 101:101 <디렉터리>`로 한 번만 맞춥니다.

## 주의 사항

- `NoNewPrivileges`와 `NET_RAW`, `NET_ADMIN` 제거를 적용합니다. 포트 80을 열고 워커 사용자로 내리는 데 필요한 권한은 남겨 둡니다.
- 상태 확인은 컨테이너 안의 `http://127.0.0.1/`를 BusyBox `wget`으로 호출합니다. 이미지에 `curl`이 없습니다. kube play는 HTTP 프로브로 `/`를 확인합니다. Quadlet은 상태 확인이 실패하면 컨테이너를 종료해 다시 시작합니다.
- 첫 화면은 트윗과 GitHub 스타 수 같은 외부 내용을 불러올 수 있습니다. 에디터의 다이어그램 저장은 브라우저 안에서 끝납니다.
- 재현이 필요하면 Compose, Quadlet, `pod.yaml`의 태그를 같은 버전으로 고정합니다.

## 참고 자료

- [drawDB](https://github.com/drawdb-io/drawdb)
- [drawDB 이미지](https://github.com/drawdb-io/drawdb/pkgs/container/drawdb)
- [drawdb-server](https://github.com/drawdb-io/drawdb-server)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
