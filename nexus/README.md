# nexus

[Sonatype Nexus Repository](https://help.sonatype.com/en/sonatype-nexus-repository.html) 저장소 관리자를 로컬에서 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

웹 UI는 `127.0.0.1:8081`에서만 열리며, `http://127.0.0.1:8081/`로 접속합니다. 이전 `docker-compose.yml`은 `8081`을 모든 인터페이스에 공개했습니다. 다른 호스트에서 저장소를 쓰려면 앞단에 리버스 프록시를 둡니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `example.env` | `.env`에 적을 키와 예시 |
| `nexus.quadlets` | Podman Quadlet (컨테이너, 볼륨) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap |
| `nginx/nexus.conf` | Nginx `server` 블록 |
| `caddy/nexus.caddyfile` | Caddy 사이트 블록 |
| `nexus_to_dt.py` | 저장소 컴포넌트를 CycloneDX SBOM으로 만들어 Dependency-Track에 업로드 |
| `nexus_to_dt_with_date.py` | 위 스크립트의 날짜 버전 및 오래된 버전 정리 기능 포함판 |

## 관리자 계정

Nexus는 첫 실행 시 `admin` 계정의 초기 비밀번호를 무작위로 만들어 `/nexus-data/admin.password`에 저장합니다. 따로 넣을 비밀값은 없습니다. 첫 로그인 후 설정 마법사에서 비밀번호를 바꾸면 이 파일은 삭제됩니다.

| 실행 방식 | 초기 비밀번호 확인 |
|---|---|
| Compose | `docker compose exec nexus cat /nexus-data/admin.password` |
| Quadlet | `podman exec nexus cat /nexus-data/admin.password` |
| kube play | `podman exec nexus-nexus cat /nexus-data/admin.password` |

## 기존 데이터

이전 구성은 `./nexus-data`를 `user: '1200:1200'`으로 바인드 마운트했습니다. 새 구성은 이름 있는 볼륨 `nexus-vol`을 쓰고, 프로세스는 이미지 기본 사용자 `nexus`(uid/gid 200)로 실행됩니다. 볼륨이 비어 있으면 새 저장소로 시작합니다.

기존 디렉터리를 이어서 쓰려면 복사한 뒤 소유권을 200:200으로 맞춥니다. Compose 볼륨 이름은 프로젝트 이름이 기본값 `nexus`일 때 `nexus_nexus-vol`입니다.

```sh
docker volume create nexus_nexus-vol
docker run --rm \
  -v "./nexus-data:/from:ro" \
  -v nexus_nexus-vol:/to \
  docker.io/library/alpine \
  sh -c "cp -a /from/. /to && chown -R 200:200 /to"
```

Quadlet·kube play로 옮길 때는 대상 볼륨 이름을 `nexus-vol`로 바꾸고 `podman`으로 실행합니다. SELinux 호스트에서는 원본 마운트에 `:z`를 붙여 `-v "./nexus-data:/from:ro,z"`로 씁니다.

이전 데이터가 3.70 이하(OrientDB)라면 최신 이미지로 바로 올릴 수 없습니다. 3.70.x에서 H2로 마이그레이션한 뒤 올립니다. 업그레이드 전에는 볼륨을 백업합니다.

## 실행

### Docker Compose

```sh
cd nexus
docker compose config
docker compose up -d
docker compose logs -f
```

로그에 `Started Sonatype Nexus`가 나올 때까지 기다립니다. 첫 실행은 2~3분이 걸립니다.

JVM 메모리를 바꾸려면 `example.env`를 참고해 `.env`에 `INSTALL4J_ADD_VM_PARAMS`를 다시 정의합니다. `.env` 값이 `default.env`보다 우선합니다.

### Podman Quadlet

Podman 5.6 이상이 필요합니다. 컨테이너 하나(`nexus`)와 이름 있는 볼륨 `nexus-vol`을 만듭니다.

이전 구성(Pod `nexus`, 컨테이너 `nexus-app`)을 설치했다면 먼저 내리고 지웁니다. 이전 Pod도 서비스 이름이 `nexus`라 남아 있으면 새 컨테이너 유닛과 겹칩니다. 볼륨 이름(`nexus-vol`)은 같으므로 데이터는 그대로 이어집니다.

```sh
systemctl --user stop nexus
podman quadlet list
podman quadlet rm nexus.pod nexus-app.container
systemctl --user daemon-reload
```

설치와 실행:

```sh
cd nexus
podman quadlet install nexus.quadlets
systemctl --user daemon-reload
systemctl --user start nexus
journalctl --user -u nexus -f
```

### podman kube play

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

`podman kube down`은 PVC 볼륨을 지우지 않습니다. 데이터까지 지우려면 `podman volume rm nexus-vol`을 따로 실행합니다.

## 리버스 프록시

`nginx/nexus.conf`와 `caddy/nexus.caddyfile`은 같은 호스트 이름(`nexus.example.com`)과 업스트림(`127.0.0.1:8081`)을 가리킵니다. 호스트 이름과 인증서 경로를 바꿔 사용합니다.

| 프록시 | 연결 방법 |
|---|---|
| Nginx | `nginx/nexus.conf`를 `/etc/nginx/conf.d/nexus.conf`로 복사하고 `nginx -t` 후 다시 읽기 |
| Caddy | Caddyfile에 `import /etc/caddy/sites/nexus.caddyfile`을 추가하고 `caddy validate --adapter caddyfile --config /etc/caddy/Caddyfile` 후 다시 읽기 |

두 설정 모두 업로드 크기를 1GB로, 읽기 타임아웃을 300초로 두고 버퍼링을 끕니다. 더 큰 아티팩트를 올리면 두 파일의 크기 제한을 함께 늘립니다. 프록시 뒤에서 열면 UI의 **Administration > System > Capabilities**에서 Base URL을 `https://nexus.example.com`으로 설정합니다.

Docker 호스팅 저장소는 커넥터 포트(예: `8082`)를 따로 씁니다. 쓰려면 Compose `ports`, Quadlet `PublishPort`, `pod.yaml` `hostPort`에 포트를 추가하고, 프록시에 해당 포트용 `server`/사이트 블록을 따로 만듭니다.

## SBOM 업로드 스크립트

`nexus_to_dt.py`, `nexus_to_dt_with_date.py`는 Nexus REST API로 저장소 컴포넌트를 수집해 Dependency-Track(`/api/v1/bom`)에 업로드합니다. 실행 전 파일 상단의 `NEXUS_USER`, `NEXUS_PASS`, `DT_API_KEY`, `REPOS`를 채웁니다. 자격 증명을 넣은 파일은 커밋하지 않습니다.

```sh
python3 nexus_to_dt.py
```

## 주의 사항

- 데이터(H2 DB, 기본 blob store, 로그)는 `/nexus-data`에 마운트한 `nexus-vol` 볼륨에 저장됩니다. 볼륨을 지우면 저장소 내용도 함께 사라집니다.
- 컨테이너는 이미지 기본 사용자 `nexus`(uid/gid 200)로 실행되고 엔트리포인트가 소유권을 바꾸지 않습니다. 이름 있는 볼륨은 Docker와 Podman 모두 처음 쓸 때 이미지의 `/nexus-data` 소유자(200:200)로 만들어지므로 `U`를 붙이지 않습니다. `U`는 기동할 때마다 볼륨 전체를 재귀적으로 `chown`하므로 blob이 많으면 기동이 느려집니다.
- 볼륨 소유권이 어긋나 `AccessDeniedException`이 나면 한 번만 맞춥니다. rootless Podman은 `podman unshare chown -R 200:200 "$(podman volume inspect -f '{{.Mountpoint}}' nexus-vol)"`, Docker는 위 [기존 데이터](#기존-데이터)의 `chown -R 200:200` 명령을 씁니다.
- 바인드 마운트로 바꾸려면 Quadlet을 `Volume=%h/.local/share/nexus:/nexus-data:Z,U`로 고칩니다. rootless Podman에서 `U`가 호스트 디렉터리를 컨테이너 uid 200에 대응하는 subuid로 바꿉니다. Docker는 `U`를 지원하지 않으므로 호스트에서 `chown -R 200:200`을 먼저 합니다.
- 외부 디스크(`/mnt/nexus`)를 blob store로 쓰려면 `compose.yaml` 또는 `nexus.quadlets`의 주석 처리된 마운트를 활성화하고 UI에서 해당 경로로 blob store를 만듭니다. Quadlet은 `U`로 소유권을 맞추고, Compose는 호스트에서 `chown -R 200:200 /mnt/nexus`를 먼저 합니다.
- SELinux 호스트에서는 Quadlet 마운트의 `:Z`가 데이터에 컨테이너 전용 레이블을 붙입니다. SELinux가 꺼진 호스트에서는 무시됩니다. Docker 이름 있는 볼륨과 kube play PVC는 엔진이 레이블을 관리하므로 붙이지 않았습니다. `/mnt/nexus`처럼 다른 서비스와 공유하는 경로라면 `:Z` 대신 `:z`를 씁니다.
- `NoNewPrivileges`와 `NET_RAW`, `NET_ADMIN` 제거를 적용합니다. 프로세스가 root가 아니므로 다른 권한도 필요하지 않습니다.
- JVM은 힙 2GB와 다이렉트 메모리 2GB를 사용하므로 호스트 메모리가 최소 6GB 이상 여유 있어야 합니다. `INSTALL4J_ADD_VM_PARAMS`를 바꾸면 이미지 기본값을 덮어쓰므로 `-Djava.util.prefs.userRoot=/nexus-data/javaprefs`를 지우지 않습니다. 값을 바꾸면 `default.env`, `nexus.quadlets`의 `Environment=`, `pod.yaml` ConfigMap `nexus-default`를 함께 수정합니다.
- 종료 시 DB가 내려가도록 120초를 기다립니다 (Compose `stop_grace_period`, Quadlet `StopTimeout`, kube play `terminationGracePeriodSeconds`). Quadlet은 systemd가 먼저 끊지 않도록 `TimeoutStopSec=150`을 둡니다.
- 첫 실행은 수 분이 걸리므로 상태 확인 시작 유예를 180초로 둡니다. 상태 확인은 `http://localhost:8081/service/rest/v1/status`를 이미지에 포함된 `curl`로 호출합니다. Quadlet은 상태 확인이 실패하면 컨테이너를 종료해 다시 시작합니다.
- 열린 파일 제한(`nofile`)은 Sonatype 권장값인 65536으로 설정합니다. `podman kube play`는 ulimit 설정을 지원하지 않으므로 Podman 기본값을 따릅니다.
- 이미지는 `docker.io/sonatype/nexus3:latest`를 씁니다. 작성 시점의 `latest`는 3.97.0(Alpine, Java 21)입니다. 3.91.0부터 기본 이미지가 Alpine 기반이고, `-ubi` 태그는 더 이상 새로 배포되지 않습니다. 다시 받을 때마다 버전이 바뀌고 버전 간 DB 마이그레이션이 있으므로 `AutoUpdate`는 쓰지 않습니다. 운영에서는 세 파일의 태그를 같은 버전으로 고정하고, 갱신 전 볼륨을 백업하고 릴리스 노트를 확인합니다.

## 참고 자료

- [Nexus Repository Docker 이미지](https://hub.docker.com/r/sonatype/nexus3)
- [docker-nexus3](https://github.com/sonatype/docker-nexus3)
- [Nexus 시스템 요구 사항](https://help.sonatype.com/en/sonatype-nexus-repository-system-requirements.html)
- [Nexus 리버스 프록시](https://help.sonatype.com/en/run-behind-a-reverse-proxy.html)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
