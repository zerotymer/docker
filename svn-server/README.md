# svn-server

[garethflowers/svn-server](https://hub.docker.com/r/garethflowers/svn-server) 이미지를 로컬에서 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

권장 실행은 컨테이너 하나입니다. 프로세스는 `svnserve`이고 저장소는 `/var/opt/svn`에 둡니다. `svn://`는 `127.0.0.1:3690`에서만 열립니다. 이 이미지는 HTTP를 제공하지 않으므로 `nginx/`, `caddy/` 설정은 두지 않습니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env` | Compose가 읽는 환경 변수 파일. 이미지가 읽는 키는 없다 |
| `svn-server.quadlets` | Podman Quadlet (컨테이너, 볼륨) |
| `pod.yaml` | `podman kube play`용 Pod, PVC |

## 이미지

게시 워크플로는 main 브랜치를 `edge`로만 올립니다. Docker Hub `latest`는 2024-11 릴리스 `1.8.1`(Alpine 3.20.3, Subversion 1.14.3)에 남아 있습니다. 이 구성은 `edge`를 씁니다. 확인한 이미지는 Alpine 3.23.3, Subversion 1.14.5-r1이고, `USER`가 없어 root로 실행됩니다.

| 항목 | 값 |
|---|---|
| 이미지 | `docker.io/garethflowers/svn-server:edge` |
| 명령 | `svnserve --daemon --foreground --root /var/opt/svn` |
| 포트 | `3690/tcp` |
| 데이터 | `/var/opt/svn` |
| 상태 확인 | `netstat -ln \| grep 3690` |

`edge`는 main이 푸시될 때마다 바뀝니다. 재현이 필요하면 세 파일의 태그를 같은 다이제스트로 고정합니다. Quadlet은 `AutoUpdate=registry`라 `podman auto-update`로 이 태그를 갱신할 수 있습니다.

## 실행

### Docker Compose

데이터는 이름 있는 볼륨 `svn-server-vol`에 저장됩니다. 프로젝트 이름은 디렉터리 이름(`svn-server`)을 따릅니다.

```sh
cd svn-server
docker compose config
docker compose up -d
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다. 컨테이너 하나와 이름 있는 볼륨 `svn-server-vol`을 만듭니다.

```sh
cd svn-server
podman quadlet install svn-server.quadlets
systemctl --user daemon-reload
systemctl --user start svn-server
```

`podman quadlet install`은 이미 설치된 파일을 덮어쓰지 않습니다. `.quadlets`를 고친 뒤에는 `podman quadlet install --replace svn-server.quadlets`, `systemctl --user daemon-reload`, `systemctl --user restart svn-server` 순서로 다시 적용합니다.

### podman kube play

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

kube play가 만드는 컨테이너 이름은 `svn-server-svn-server`입니다.

## 저장소

이미지에는 저장소가 들어 있지 않습니다. 첫 저장소는 컨테이너 안에서 `svnadmin`으로 만듭니다. 아래 예시는 저장소 이름이 `sample`이고 사용자 이름이 `alice`입니다. `<비밀번호>`는 실행 전에 바꿉니다. 비밀번호는 볼륨 안 `conf/passwd`에만 있으며 이 저장소에 커밋하지 않습니다.

```sh
docker compose exec svn-server svnadmin create sample
docker compose exec svn-server sh -c '
  sed -i \
    -e "s/^# anon-access = read/anon-access = read/" \
    -e "s/^# auth-access = write/auth-access = write/" \
    -e "s/^# password-db = passwd/password-db = passwd/" \
    -e "s/^# realm = My First Repository/realm = sample/" \
    sample/conf/svnserve.conf
  printf "[users]\nalice = <비밀번호>\n" > sample/conf/passwd
  chmod 600 sample/conf/passwd
'
```

Quadlet은 `podman exec svn-server`, kube play는 `podman exec svn-server-svn-server`로 같은 명령을 실행합니다. `svnserve.conf` 기본값은 주석 처리되어 있고, 그 상태의 동작은 익명 읽기와 인증된 쓰기입니다. `password-db`를 열기 전에는 인증할 사용자가 없어 쓰기가 거부됩니다.

접속 주소는 `svn://127.0.0.1/sample`입니다.

```sh
svn info svn://127.0.0.1/sample
svn checkout svn://127.0.0.1/sample
```

`conf/authz`는 경로별 권한이 필요할 때 `authz-db = authz`로 엽니다. 열지 않으면 인증된 사용자는 저장소 전체를 쓸 수 있습니다.

## 주의 사항

- 호스트 포트는 `127.0.0.1:3690`입니다. 다른 호스트에서 `svn://`로 접속하려면 포트 바인딩의 `127.0.0.1:`을 제거합니다. 익명 읽기가 기본이라, 모든 인터페이스에 열기 전에 `anon-access = none`으로 바꿉니다.
- 컨테이너 안 `svnserve`는 `0.0.0.0:3690`에서 수신합니다. `--listen-host 127.0.0.1`로 바꾸면 호스트로 발행한 포트에 연결되지 않습니다.
- 데이터는 `/var/opt/svn`에 마운트한 `svn-server-vol`에 있습니다. 볼륨을 지우면 저장소도 함께 사라집니다. Compose 볼륨 이름은 프로젝트 이름이 `svn-server`일 때 `svn-server_svn-server-vol`입니다.
- 이미지는 root로 실행되고 엔트리포인트가 소유권을 바꾸지 않습니다. 이름 있는 볼륨은 처음 쓸 때 root가 쓸 수 있으므로 `U`를 붙이지 않습니다. `U`는 기동할 때마다 저장소 전체를 재귀적으로 `chown`합니다.
- 볼륨 소유권이 어긋나 `svnadmin`이나 커밋이 `Permission denied`로 실패하면 한 번만 맞춥니다. rootless Podman은 `podman unshare chown -R 0:0 "$(podman volume inspect -f '{{.Mountpoint}}' svn-server-vol)"`입니다. Docker는 `docker run --rm -v svn-server_svn-server-vol:/var/opt/svn docker.io/garethflowers/svn-server:edge chown -R 0:0 /var/opt/svn`입니다.
- 바인드 마운트로 바꾸려면 디렉터리를 먼저 만듭니다. Compose는 `./data:/var/opt/svn:Z`, Quadlet은 `Volume=%h/.local/share/svn-server:/var/opt/svn:Z`입니다. `./data`는 저장소 `.gitignore`의 `data/**`에 걸립니다.
- rootful Docker의 바인드 마운트에서 만든 파일은 호스트 root 소유가 됩니다. rootless Podman에서는 컨테이너 root가 호스트 사용자라, 그 사용자 소유의 디렉터리는 그대로 쓸 수 있습니다. 다른 uid의 기존 저장소를 붙일 때는 `podman unshare chown -R 0:0 <디렉터리>`로 맞춥니다. Docker는 `U`를 지원하지 않으므로 호스트에서 root가 디렉터리를 쓸 수 있게 맞춥니다.
- 컨테이너 사용자를 root가 아닌 uid로 바꾸면 이미지에는 소유권을 고쳐 주는 엔트리포인트가 없습니다. 데이터 디렉터리를 그 uid로 `chown`한 뒤에 기동합니다.
- SELinux 호스트에서는 바인드 마운트에 `:Z`를 붙입니다. 레이블이 없으면 쓰기가 거부됩니다. SELinux가 꺼진 호스트에서는 `:Z`가 무시됩니다. Docker 이름 있는 볼륨과 kube play PVC는 엔진이 레이블을 관리하므로 붙이지 않았습니다. Quadlet 이름 있는 볼륨에는 `:Z`를 붙입니다. 다른 컨테이너와 같은 디렉터리를 공유하면 `:Z` 대신 `:z`를 씁니다.
- `conf/passwd`는 `chmod 600`으로 둡니다. 볼륨을 호스트에서 열었을 때 다른 사용자가 비밀번호를 읽지 못하게 합니다.
- 상태 확인은 이미지와 같이 `netstat -ln | grep 3690`입니다. 포트가 열려 있는지만 보며 인증은 확인하지 않습니다. Quadlet은 상태 확인이 실패하면 컨테이너를 종료해 다시 시작합니다. Compose는 상태 확인 실패만으로 다시 시작하지 않습니다.
- 같은 호스트의 다른 스택은 `3690`을 쓰지 않습니다. 호스트에 `svnserve`가 이미 있으면 포트가 겹칩니다.

## 참고 자료

- [svn-server 이미지](https://hub.docker.com/r/garethflowers/svn-server)
- [docker-svn-server](https://github.com/garethflowers/docker-svn-server)
- [svnserve 설정](https://svnbook.red-bean.com/en/1.7/svn.serverconfig.svnserve.html)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
