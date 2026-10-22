# pgmq

[pgmq](https://github.com/pgmq/pgmq) 확장이 포함된 PostgreSQL 18을 로컬에서 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다. 확장 없는 공식 이미지는 상위 `postgresql/` 구성을 사용합니다.

데이터베이스는 `127.0.0.1:5432`에서만 열리며, 기본 데이터베이스는 `pgmq_lab`, 사용자는 `postgres`입니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `example.env` | `.env`에 적을 키와 예시 |
| `init/01-pgmq.sql` | 최초 초기화 스크립트 (pgmq 확장 및 `test_queue` 생성) |
| `pgmq.quadlets` | Podman Quadlet (컨테이너) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap, Secret |

## 비밀번호

저장소에 있는 기본 비밀번호(`postgres`)는 예제 값이므로 실행 전에 직접 생성한 값으로 바꿉니다.

```sh
openssl rand -hex 32
```

| 실행 방식 | 비밀번호 전달 방법 |
|---|---|
| Compose | `example.env`를 `.env`로 복사한 뒤 `POSTGRES_PASSWORD` 입력 |
| Quadlet | podman secret `pgmq-password`를 미리 생성 |
| kube play | `pod.yaml`의 Secret `POSTGRES_PASSWORD` 값을 교체 |

## 실행

### Docker Compose

```sh
cd postgresql/pgmq
cp example.env .env # POSTGRES_PASSWORD 입력
docker compose config
docker compose up -d
```

`.env`의 빈 값도 `default.env` 값을 덮어쓰므로 바꿀 키만 남깁니다.

접속 확인은 다음과 같습니다.

```sh
docker compose exec pgmq psql -U postgres -d pgmq_lab -c "SELECT * FROM pgmq.list_queues();"
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다. Pod 없이 컨테이너 하나로 실행하며, 데이터는 `~/.local/share/pgmq/data`, 초기화 스크립트는 `~/.local/share/pgmq/init`에 둡니다. 디렉터리는 서비스 시작 전에 `ExecStartPre`가 만들지만, 초기화 스크립트는 첫 시작 전에 직접 복사합니다.

```sh
cd postgresql/pgmq
mkdir -p ~/.local/share/pgmq/init
cp init/*.sql ~/.local/share/pgmq/init/
# /run은 root만 쓸 수 있으므로 소켓 디렉터리를 한 번 만든다. 재부팅해도 다시 만든다
echo "d /run/postgresql 0700 $(id -un) $(id -gn) -" | sudo tee /etc/tmpfiles.d/postgresql.conf
sudo systemd-tmpfiles --create /etc/tmpfiles.d/postgresql.conf
openssl rand -hex 32 | tr -d '\n' | podman secret create pgmq-password -
podman quadlet install pgmq.quadlets
systemctl --user daemon-reload
systemctl --user start pgmq
```

`podman quadlet install`은 이미 설치된 파일을 덮어쓰지 않습니다. `.quadlets`를 고친 뒤에는 `podman quadlet install --replace pgmq.quadlets`, `systemctl --user daemon-reload`, `systemctl --user restart pgmq` 순서로 다시 적용합니다. 적용 여부는 `systemctl --user cat pgmq`으로 확인합니다.

비밀번호 확인은 다음과 같습니다.

```sh
podman secret inspect --showsecret --format '{{.SecretData}}' pgmq-password
```

유닉스 소켓은 호스트의 `/run/postgresql`에 공유합니다. 호스트 `psql`의 기본 소켓 경로라 `-h` 없이 접속합니다.

```sh
psql -U postgres -d pgmq_lab
```

sudo를 쓸 수 없으면 `pgmq.quadlets`의 주석대로 `Volume=%t/pgmq:/var/run/postgresql:Z`와 `RuntimeDirectory=pgmq`, `RuntimeDirectoryMode=0700`을 켜고 `/run/postgresql` 줄을 지웁니다. systemd가 서비스 시작 전에 `/run/user/<UID>/pgmq`을 만들고 멈출 때 지웁니다. 접속은 `psql -h "$XDG_RUNTIME_DIR/pgmq" -U postgres -d pgmq_lab`로 하며, `PGHOST`에 넣으면 `-h`를 생략할 수 있습니다.

`POSTGRES_DB`, `POSTGRES_USER`를 바꾸면 `HealthCmd`의 `pg_isready` 인자도 같은 값으로 수정합니다. systemd가 `$`를 확장하므로 환경 변수를 참조하지 않고 값을 직접 적습니다.

rootful로 실행할 때는 `UserNS=` 줄을 빼고 tmpfiles 소유자를 컨테이너 postgres와 같은 `999 999`로 바꿉니다. `%h`가 `/root`이므로 데이터는 `/root/.local/share/pgmq`에 저장됩니다.

### podman kube play

`pod.yaml`의 `POSTGRES_PASSWORD` 값을 교체한 뒤 실행합니다. 비밀번호를 넣은 `pod.yaml`은 커밋하지 않습니다.

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

초기화 스크립트는 `pod.yaml`의 ConfigMap `pgmq-init`에 포함되어 있습니다. `init/01-pgmq.sql`을 수정하면 이 ConfigMap도 같은 내용으로 맞춥니다.

## 주의 사항

- 상위 `postgresql/`과 같은 `127.0.0.1:5432`를 씁니다. 함께 실행하려면 한쪽 호스트 포트를 바꿉니다.
- `POSTGRES_*` 환경 변수와 초기화 스크립트는 데이터 디렉터리가 비어 있을 때 한 번만 적용됩니다. 이후 비밀번호를 바꾸려면 `ALTER USER`를 실행하거나 데이터를 지우고 다시 초기화합니다.
- PostgreSQL 18 이미지는 데이터 디렉터리를 `/var/lib/postgresql/18/docker`에 만들기 때문에 `/var/lib/postgresql`에 마운트합니다.
- 공유 메모리는 256MB로 설정합니다 (Compose `shm_size`, Quadlet `ShmSize`, kube play 메모리 `emptyDir`).
- Quadlet은 `UserNS=keep-id:uid=999,gid=999`로 컨테이너의 `postgres`(uid 999)를 호스트 사용자에 매핑합니다. 데이터와 소켓 파일이 호스트 사용자 소유가 되어 `podman unshare` 없이 백업하거나 지울 수 있습니다. 이미지가 root로 시작해 소유권을 직접 맞추므로 마운트에 `U`는 붙이지 않습니다. 이전 구성(매핑 없음)으로 만든 `~/.local/share/pgmq/data`는 소유자가 subuid로 남아 있으니 `podman unshare rm -rf ~/.local/share/pgmq/data`로 지우고 다시 초기화합니다. `keep-id`는 rootless 전용이라 rootful로 실행할 때는 `UserNS=` 줄을 뺍니다.
- SELinux 호스트에서는 바인드 마운트에 `:Z`를 붙입니다. SELinux가 꺼진 호스트에서는 무시됩니다.
- 소켓 디렉터리 `/run/postgresql`은 `/etc/tmpfiles.d/postgresql.conf`가 호스트 사용자 소유 `0700`으로 만듭니다. `/run`은 재부팅하면 비워지지만 `systemd-tmpfiles`가 부팅할 때마다 다시 만들므로 따로 할 일은 없습니다. 디렉터리가 없으면 컨테이너가 `statfs ... no such file or directory`로 시작하지 않습니다.
- 공식 이미지의 `pg_hba.conf`는 유닉스 소켓 접속을 `trust`로 허용합니다. 소켓 디렉터리가 `0700`이라 그 사용자만 비밀번호 없이 접속하며, 권한을 넓히면 다른 사용자도 슈퍼유저로 접속합니다.
- 호스트에 PostgreSQL 패키지가 설치되어 있으면 `/run/postgresql`과 5432 소켓이 겹칩니다. `postgresql/`과 `pgmq/`도 같은 소켓 경로를 쓰므로 하나만 실행합니다. Compose와 kube play는 소켓을 공유하지 않습니다.
- 이전 Quadlet이 만든 이름 있는 볼륨 `postgresql-vol`은 더 이상 쓰지 않습니다. 데이터가 필요 없으면 `podman volume rm postgresql-vol`로 지웁니다.
- TCP 서비스라 `nginx/`, `caddy/` 프록시 설정은 두지 않습니다.
- 이미지는 `ghcr.io/pgmq/pg18-pgmq:v1.10.0`으로 고정되어 있습니다. 갱신할 때는 pgmq 확장 버전 호환성을 확인하고 세 파일의 태그를 같이 바꿉니다.

## 참고 자료

- [pgmq](https://github.com/pgmq/pgmq)
- [PostgreSQL Docker 공식 이미지](https://hub.docker.com/_/postgres)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
