# postgresql

공식 [PostgreSQL](https://hub.docker.com/_/postgres) 이미지를 로컬에서 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

데이터베이스는 `127.0.0.1:5432`에서만 열리며, 기본 데이터베이스와 사용자는 모두 `postgres`입니다. [pgmq](https://github.com/pgmq/pgmq) 확장이 필요하면 [`pgmq/`](pgmq/README.md) 구성을 사용합니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose (주 버전별 프로필 `16`, `17`, `18`) |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `example.env` | `.env`에 적을 키와 예시 |
| `postgresql.quadlets` | Podman Quadlet (컨테이너, PostgreSQL 18) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap, Secret (PostgreSQL 18) |
| `pgmq/` | pgmq 확장 이미지 구성 |

## 비밀번호

저장소에 있는 기본 비밀번호(`postgres`)는 예제 값이므로 실행 전에 직접 생성한 값으로 바꿉니다.

```sh
openssl rand -hex 32
```

| 실행 방식 | 비밀번호 전달 방법 |
|---|---|
| Compose | `example.env`를 `.env`로 복사한 뒤 `POSTGRES_PASSWORD` 입력 |
| Quadlet | podman secret `postgresql-password`를 미리 생성 |
| kube play | `pod.yaml`의 Secret `POSTGRES_PASSWORD` 값을 교체 |

## 실행

### Docker Compose

주 버전마다 서비스와 프로필이 하나씩 있습니다. 모든 서비스에 프로필이 붙어 있어 프로필 없이 `up`하면 아무것도 뜨지 않습니다.

| 프로필 | 서비스 | 이미지 | 볼륨 | 마운트 경로 |
|---|---|---|---|---|
| `18` | `postgresql-18` | `postgres:18` | `postgresql-18-data` | `/var/lib/postgresql` |
| `17` | `postgresql-17` | `postgres:17` | `postgresql-17-data` | `/var/lib/postgresql/data` |
| `16` | `postgresql-16` | `postgres:16` | `postgresql-16-data` | `/var/lib/postgresql/data` |

```sh
cd postgresql
cp example.env .env # POSTGRES_PASSWORD 입력
docker compose --profile 18 config
docker compose --profile 18 up -d
docker compose --profile 18 down
```

매번 `--profile`을 적지 않으려면 `.env`에 `COMPOSE_PROFILES=18`을 넣습니다. `.env`의 빈 값도 `default.env` 값을 덮어쓰므로 바꿀 키만 남깁니다.

접속 확인은 다음과 같습니다.

```sh
docker compose --profile 18 exec postgresql-18 psql -U postgres -c "SELECT version();"
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다. Pod 없이 컨테이너 하나로 PostgreSQL 18을 실행하며, 데이터는 `~/.local/share/postgresql`에 저장합니다. 디렉터리는 서비스 시작 전에 `ExecStartPre`가 만듭니다. secret은 한 번만 생성하면 재시작해도 유지됩니다.

```sh
# /run은 root만 쓸 수 있으므로 소켓 디렉터리를 한 번 만든다. 재부팅해도 다시 만든다
echo "d /run/postgresql 0700 $(id -un) $(id -gn) -" | sudo tee /etc/tmpfiles.d/postgresql.conf
sudo systemd-tmpfiles --create /etc/tmpfiles.d/postgresql.conf
openssl rand -hex 32 | tr -d '\n' | podman secret create postgresql-password -
podman quadlet install postgresql.quadlets
systemctl --user daemon-reload
systemctl --user start postgresql
```

`podman quadlet install`은 이미 설치된 파일을 덮어쓰지 않습니다. `.quadlets`를 고친 뒤에는 `podman quadlet install --replace postgresql.quadlets`, `systemctl --user daemon-reload`, `systemctl --user restart postgresql` 순서로 다시 적용합니다. 적용 여부는 `systemctl --user cat postgresql`으로 확인합니다.

비밀번호 확인은 다음과 같습니다.

```sh
podman secret inspect --showsecret --format '{{.SecretData}}' postgresql-password
```

유닉스 소켓은 호스트의 `/run/postgresql`에 공유합니다. 호스트 `psql`의 기본 소켓 경로라 `-h` 없이 접속합니다.

```sh
psql -U postgres -d postgres
```

sudo를 쓸 수 없으면 `postgresql.quadlets`의 주석대로 `Volume=%t/postgresql:/var/run/postgresql:Z`와 `RuntimeDirectory=postgresql`, `RuntimeDirectoryMode=0700`을 켜고 `/run/postgresql` 줄을 지웁니다. systemd가 서비스 시작 전에 `/run/user/<UID>/postgresql`을 만들고 멈출 때 지웁니다. 접속은 `psql -h "$XDG_RUNTIME_DIR/postgresql" -U postgres -d postgres`로 하며, `PGHOST`에 넣으면 `-h`를 생략할 수 있습니다.

`POSTGRES_DB`, `POSTGRES_USER`를 바꾸면 `HealthCmd`의 `pg_isready` 인자도 같은 값으로 수정합니다. systemd가 `$`를 확장하므로 환경 변수를 참조하지 않고 값을 직접 적습니다.

다른 주 버전을 쓰려면 `Image=` 태그를 바꿉니다. 17 이하는 마운트 경로를 `/var/lib/postgresql/data`로 바꾸고, 기존 데이터 디렉터리는 다른 주 버전으로 그대로 열 수 없습니다.

rootful로 실행할 때는 `UserNS=` 줄을 빼고 tmpfiles 소유자를 컨테이너 postgres와 같은 `999 999`로 바꿉니다. `%h`가 `/root`이므로 데이터는 `/root/.local/share/postgresql`에 저장됩니다.

### podman kube play

`pod.yaml`의 `POSTGRES_PASSWORD` 값을 교체한 뒤 실행합니다. 비밀번호를 넣은 `pod.yaml`은 커밋하지 않습니다.

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

## 주의 사항

- 프로필마다 같은 `127.0.0.1:5432`를 씁니다. 두 버전을 함께 띄우려면 한쪽 호스트 포트를 바꿉니다. `pgmq/`도 같은 포트를 씁니다.
- 주 버전마다 볼륨이 따로 있습니다. 버전을 올려도 데이터는 옮겨지지 않으며 `pg_dumpall`/복원이나 `pg_upgrade`로 옮깁니다.
- `POSTGRES_*` 환경 변수는 데이터 디렉터리가 비어 있을 때 한 번만 적용됩니다. 이후 비밀번호를 바꾸려면 `ALTER USER`를 실행하거나 데이터를 지우고 다시 초기화합니다.
- PostgreSQL 18 이미지부터 데이터 디렉터리가 `/var/lib/postgresql/18/docker`로 바뀌어 `/var/lib/postgresql`에 마운트합니다. 17 이하는 `/var/lib/postgresql/data`입니다.
- 공유 메모리는 256MB로 설정합니다 (Compose `shm_size`, Quadlet `ShmSize`, kube play 메모리 `emptyDir`).
- Quadlet은 `UserNS=keep-id:uid=999,gid=999`로 컨테이너의 `postgres`(uid 999)를 호스트 사용자에 매핑합니다. 데이터와 소켓 파일이 호스트 사용자 소유가 되어 `podman unshare` 없이 백업하거나 지울 수 있습니다. 이미지가 root로 시작해 소유권을 직접 맞추므로 마운트에 `U`는 붙이지 않습니다. 이전 구성(매핑 없음)으로 만든 `~/.local/share/postgresql`는 소유자가 subuid로 남아 있으니 `podman unshare rm -rf ~/.local/share/postgresql`로 지우고 다시 초기화합니다. `keep-id`는 rootless 전용이라 rootful로 실행할 때는 `UserNS=` 줄을 뺍니다.
- SELinux 호스트에서는 Quadlet 바인드 마운트에 `:Z`를 붙입니다. SELinux가 꺼진 호스트에서는 무시됩니다.
- 이전 Quadlet이 만든 이름 있는 볼륨 `postgresql-vol`은 더 이상 쓰지 않습니다. 데이터가 필요 없으면 `podman volume rm postgresql-vol`로 지웁니다.
- 소켓 디렉터리 `/run/postgresql`은 `/etc/tmpfiles.d/postgresql.conf`가 호스트 사용자 소유 `0700`으로 만듭니다. `/run`은 재부팅하면 비워지지만 `systemd-tmpfiles`가 부팅할 때마다 다시 만들므로 따로 할 일은 없습니다. 디렉터리가 없으면 컨테이너가 `statfs ... no such file or directory`로 시작하지 않습니다.
- 공식 이미지의 `pg_hba.conf`는 유닉스 소켓 접속을 `trust`로 허용합니다. 소켓 디렉터리가 `0700`이라 그 사용자만 비밀번호 없이 접속하며, 권한을 넓히면 다른 사용자도 슈퍼유저로 접속합니다.
- 호스트에 PostgreSQL 패키지가 설치되어 있으면 `/run/postgresql`과 5432 소켓이 겹칩니다. `postgresql/`과 `pgmq/`도 같은 소켓 경로를 쓰므로 하나만 실행합니다. Compose와 kube play는 소켓을 공유하지 않습니다.
- TCP 서비스라 `nginx/`, `caddy/` 프록시 설정은 두지 않습니다.
- 이미지는 주 버전 태그(`postgres:18` 등)로 고정되어 있습니다. 부 버전까지 고정하려면 태그를 `18.x`처럼 바꾸고 Quadlet, `pod.yaml`도 같이 맞춥니다.

## 참고 자료

- [PostgreSQL Docker 공식 이미지](https://hub.docker.com/_/postgres)
- [Compose 프로필](https://docs.docker.com/compose/how-tos/profiles/)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
