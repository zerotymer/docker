# postgresql

[pgmq](https://github.com/pgmq/pgmq) 확장이 포함된 PostgreSQL 18을 로컬에서 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

데이터베이스는 `127.0.0.1:5432`에서만 열리며, 기본 데이터베이스는 `pgmq_lab`, 사용자는 `postgres`입니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env`, `.env.example` | Compose 환경 변수 (`.env`는 선택) |
| `init/01-pgmq.sql` | 최초 초기화 스크립트 (pgmq 확장 및 `test_queue` 생성) |
| `postgresql.quadlets` | Podman Quadlet (Pod, 볼륨, 컨테이너) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap, Secret |
| `pgmq/` | 이전 Compose 구성 (모든 인터페이스에 5432 공개) |

## 비밀번호

저장소에 있는 기본 비밀번호(`postgres`)는 예제 값이므로 실행 전에 직접 생성한 값으로 바꿉니다.

```sh
openssl rand -hex 32
```

| 실행 방식 | 비밀번호 전달 방법 |
|---|---|
| Compose | `.env.example`을 `.env`로 복사한 뒤 `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` 입력 |
| Quadlet | podman secret `postgresql-password`를 미리 생성 |
| kube play | `pod.yaml`의 Secret `POSTGRES_PASSWORD` 값을 교체 |

## 실행

### Docker Compose

```sh
cd postgresql
cp .env.example .env # POSTGRES_* 값 입력
docker compose config
docker compose up -d
```

`.env`의 빈 값도 `default.env` 값을 덮어쓰므로 `.env`를 쓸 때는 세 값을 모두 채웁니다.

접속 확인은 다음과 같습니다.

```sh
docker compose exec postgres psql -U postgres -d pgmq_lab -c "SELECT * FROM pgmq.list_queues();"
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다. 초기화 스크립트를 사용자 데이터 디렉터리에 복사하고 secret을 한 번 생성합니다. secret은 재시작해도 유지됩니다.

```sh
mkdir -p ~/.local/share/postgresql/init
cp init/*.sql ~/.local/share/postgresql/init/
openssl rand -hex 32 | tr -d '\n' | podman secret create postgresql-password -
podman quadlet install postgresql.quadlets
systemctl --user daemon-reload
systemctl --user start postgresql
```

비밀번호 확인은 다음과 같습니다.

```sh
podman secret inspect --showsecret --format '{{.SecretData}}' postgresql-password
```

`POSTGRES_DB`, `POSTGRES_USER`를 바꾸면 `HealthCmd`의 `pg_isready` 인자도 같은 값으로 수정합니다. systemd가 `$`를 확장하므로 환경 변수를 참조하지 않고 값을 직접 적습니다.

### podman kube play

`pod.yaml`의 `POSTGRES_PASSWORD` 값을 교체한 뒤 실행합니다. 비밀번호를 넣은 `pod.yaml`은 커밋하지 않습니다.

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

초기화 스크립트는 `pod.yaml`의 ConfigMap `postgresql-init`에 포함되어 있습니다. `init/01-pgmq.sql`을 수정하면 이 ConfigMap도 같은 내용으로 맞춥니다.

## 주의 사항

- `POSTGRES_*` 환경 변수와 초기화 스크립트는 데이터 볼륨이 비어 있을 때 한 번만 적용됩니다. 이후 비밀번호를 바꾸려면 `ALTER USER`를 실행하거나 볼륨을 지우고 다시 초기화합니다.
- PostgreSQL 18 이미지는 데이터 디렉터리를 `/var/lib/postgresql/18/docker`에 만들기 때문에 볼륨을 `/var/lib/postgresql`에 마운트합니다.
- 공유 메모리는 256MB로 설정합니다 (Compose `shm_size`, Quadlet `--shm-size`, kube play 메모리 `emptyDir`).
- 이미지는 `ghcr.io/pgmq/pg18-pgmq:v1.10.0`으로 고정되어 있습니다. 갱신할 때는 pgmq 확장 버전 호환성을 확인합니다.

## 참고 자료

- [pgmq](https://github.com/pgmq/pgmq)
- [PostgreSQL Docker 공식 이미지](https://hub.docker.com/_/postgres)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
