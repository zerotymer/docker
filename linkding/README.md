# linkding

[linkding](https://linkding.link/) 북마크 관리 서비스를 로컬에서 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

웹 UI는 `127.0.0.1:9090`에서만 열리며, `http://127.0.0.1:9090/`로 접속합니다. 다른 호스트에서 접속하려면 앞단에 리버스 프록시를 둡니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `example.env` | `.env`에 적을 키와 예시 |
| `linkding.quadlets` | Podman Quadlet (컨테이너, 볼륨) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap, Secret |
| `nginx/linkding.conf` | Nginx `server` 블록 |
| `caddy/linkding.caddyfile` | Caddy 사이트 블록 |

## 관리자 계정

첫 실행 시 `LD_SUPERUSER_NAME`, `LD_SUPERUSER_PASSWORD` 값으로 관리자 계정을 만듭니다. `default.env`와 `pod.yaml`에 있는 기본 비밀번호(`password`)는 예제 값이므로 실행 전에 바꿉니다.

| 실행 방식 | 비밀번호 전달 방법 |
|---|---|
| Compose | `.env`를 만들고 `LD_SUPERUSER_PASSWORD`를 입력 (`default.env`보다 우선) |
| Quadlet | podman secret `linkding-superuser-password`를 미리 생성 |
| kube play | `pod.yaml`의 Secret `LD_SUPERUSER_PASSWORD` 값을 base64로 교체 |

관리자 계정은 데이터 볼륨에 사용자가 없을 때만 만들어집니다. 이미 계정이 생성된 뒤에는 환경 변수를 바꿔도 비밀번호가 바뀌지 않으므로 UI 설정이나 아래 명령으로 변경합니다.

```sh
docker compose exec linkding python manage.py changepassword admin
podman exec -it linkding python manage.py changepassword admin
```

## 실행

### Docker Compose

```sh
cd linkding
printf 'LD_SUPERUSER_PASSWORD=%s\n' "$(openssl rand -hex 16)" > .env
docker compose config
docker compose up -d
```

다른 기본값을 바꾸려면 `example.env`를 참고해 필요한 키만 `.env`에 적습니다.

### Podman Quadlet

Podman 5.6 이상이 필요합니다. 컨테이너 하나와 이름 있는 볼륨 `linkding-vol`을 만듭니다.

이전 구성(Pod `linkding`, 컨테이너 `linkding-container`)을 설치했다면 먼저 내리고 지웁니다. 이전 Pod도 서비스 이름이 `linkding`이라 남아 있으면 새 컨테이너 유닛과 겹칩니다. 볼륨 이름(`linkding-vol`)은 같으므로 데이터는 그대로 이어집니다.

```sh
systemctl --user stop linkding
podman quadlet list
podman quadlet rm linkding.pod linkding-app.container
systemctl --user daemon-reload
```

서비스를 실행할 사용자 계정에서 secret을 한 번 생성합니다. secret은 재시작해도 유지됩니다.

```sh
cd linkding
printf '%s' '<비밀번호>' | podman secret create linkding-superuser-password -
podman quadlet install linkding.quadlets
systemctl --user daemon-reload
systemctl --user start linkding
```

컨테이너는 `AutoUpdate=registry`로 설정되어 있어 `podman auto-update`로 이미지를 갱신할 수 있습니다.

### podman kube play

`pod.yaml`의 `LD_SUPERUSER_PASSWORD` 값을 교체한 뒤 실행합니다. 비밀번호를 넣은 `pod.yaml`은 커밋하지 않습니다.

```sh
printf '%s' '<비밀번호>' | base64
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

## 리버스 프록시

`nginx/linkding.conf`와 `caddy/linkding.caddyfile`은 같은 호스트 이름(`linkding.example.com`)과 업스트림(`127.0.0.1:9090`)을 가리킵니다. 호스트 이름과 인증서 경로를 바꿔 사용합니다.

| 프록시 | 연결 방법 |
|---|---|
| Nginx | `nginx/linkding.conf`를 `/etc/nginx/conf.d/linkding.conf`로 복사하고 `nginx -t` 후 다시 읽기 |
| Caddy | Caddyfile에 `import /etc/caddy/sites/linkding.caddyfile`을 추가하고 `caddy validate --adapter caddyfile --config /etc/caddy/Caddyfile` 후 다시 읽기 |

HTTPS 주소로 열면 `.env`(Quadlet은 `Environment=`, kube play는 ConfigMap)에 `LD_CSRF_TRUSTED_ORIGINS=https://linkding.example.com`을 설정합니다. 설정하지 않으면 로그인 같은 POST 요청이 CSRF 오류로 거부됩니다. 북마크 가져오기와 업로드를 위해 두 설정 모두 요청 크기를 100MB로 둡니다.

## 주의 사항

- 데이터(SQLite DB, 파비콘, 미리보기 등)는 `/etc/linkding/data`에 마운트한 `linkding-vol` 볼륨에 저장됩니다. 볼륨을 지우면 북마크도 함께 사라집니다.
- 이미지 엔트리포인트는 root로 시작해 데이터 디렉터리를 `www-data`(UID 33)로 `chown`한 뒤 그 사용자로 서버를 실행합니다. 따라서 마운트에 `U`를 붙이지 않습니다. rootless Podman에서는 볼륨 파일이 호스트의 subuid 소유가 되므로 직접 확인할 때는 `podman unshare ls -ln "$(podman volume inspect -f '{{.Mountpoint}}' linkding-vol)"`처럼 `podman unshare`를 씁니다.
- 바인드 마운트로 바꾸려면 디렉터리를 먼저 만들고(`mkdir -p ~/.local/share/linkding`) Quadlet을 `Volume=%h/.local/share/linkding:/etc/linkding/data:Z`로 고칩니다. 소유자는 엔트리포인트가 맞추므로 따로 `chown`하지 않습니다.
- SELinux 호스트에서는 Quadlet 마운트의 `:Z`가 데이터에 컨테이너 전용 레이블을 붙입니다. SELinux가 꺼진 호스트에서는 무시됩니다. Docker 이름 있는 볼륨과 kube play PVC는 엔진이 레이블을 관리하므로 붙이지 않았습니다.
- `NoNewPrivileges`와 `NET_RAW`, `NET_ADMIN` 제거를 적용합니다. 엔트리포인트의 `chown`과 사용자 전환에 필요한 `CHOWN`, `SETUID`, `SETGID`는 남겨 둡니다.
- 같은 호스트의 `prometheus`도 `9090`을 사용합니다. 함께 실행하려면 한쪽 호스트 포트를 바꾸고 프록시 업스트림도 함께 고칩니다.
- 상태 확인은 `http://localhost:9090/health` 엔드포인트를 사용합니다. Quadlet은 상태 확인이 실패하면 컨테이너를 종료해 다시 시작합니다.
- 이미지는 `latest-alpine`을 사용합니다. 재현성이 필요하면 세 파일의 태그를 같은 버전으로 고정합니다.

## 참고 자료

- [linkding 설치](https://linkding.link/installation/)
- [linkding 옵션](https://linkding.link/options/)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
