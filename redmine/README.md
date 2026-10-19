# redmine

[Redmine](https://www.redmine.org/) 프로젝트 관리 도구를 로컬에서 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

권장 실행은 컨테이너 하나입니다. DB를 지정하지 않으면 공식 이미지가 SQLite(`sqlite/redmine.db`)로 동작합니다. Quadlet과 `pod.yaml`은 이 SQLite 구성만 정의합니다. Compose는 같은 포트를 쓰는 데이터베이스를 프로필로 나누며, 프로필 없이 `up`하면 아무것도 뜨지 않습니다.

웹 UI는 `127.0.0.1:3080`에서만 열리며, `http://127.0.0.1:3080/`로 접속합니다. 컨테이너 안 포트는 `3000`이지만 같은 호스트의 `gitea`, `adguard`가 호스트 `3000`을 쓰므로 `3080`으로 공개합니다. 다른 호스트에서 접속하려면 [리버스 프록시](#리버스-프록시)를 앞에 둡니다.

SQLite는 사용자가 여럿인 운영에는 맞지 않습니다. 그 경우에는 `postgres` 프로필을 씁니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose (프로필 `sqlite`, `postgres`, `mysql`) |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `example.env` | `.env`에 적을 키와 예시 |
| `redmine.quadlets` | Podman Quadlet (컨테이너 하나, SQLite) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap, Secret (SQLite) |
| `nginx/redmine.conf` | Nginx `server` 블록 |
| `caddy/redmine.caddyfile` | Caddy 사이트 블록 |

## 관리자 계정

첫 실행 때 `rake db:migrate`가 스키마를 만들고 관리자 계정 `admin`(비밀번호 `admin`)을 만듭니다. 로그인한 뒤 바로 비밀번호를 바꿉니다.

트래커, 상태, 역할 같은 기본 데이터는 자동으로 들어가지 않습니다. 관리 화면에서 언어를 고르고 기본 설정을 불러오거나, 명령으로 넣습니다.

```sh
docker compose --profile sqlite exec redmine rake redmine:load_default_data REDMINE_LANG=ko
# Quadlet: podman exec redmine rake redmine:load_default_data REDMINE_LANG=ko
# kube play: podman exec redmine-redmine rake redmine:load_default_data REDMINE_LANG=ko
```

## 비밀값

| 값 | 용도 | 비워 두면 |
|---|---|---|
| `SECRET_KEY_BASE` | 세션 쿠키 서명 키. 공식 이미지의 `REDMINE_SECRET_KEY_BASE`는 같은 값의 옛 이름입니다 | 엔트리포인트가 컨테이너 안에 만들고, 컨테이너를 다시 만들 때마다 모든 로그인이 풀립니다 |
| `REDMINE_DB_PASSWORD` | `postgres`, `mysql` 프로필의 DB 비밀번호. 앱과 DB가 같은 값을 씁니다 | 기본값 `redmine` |
| `MYSQL_ROOT_PASSWORD` | `mysql` 프로필의 root 비밀번호 | 기본값 `redmine` |

`default.env`의 `SECRET_KEY_BASE=redmine`은 예제 값입니다. 다른 사람과 이 인스턴스를 쓰기 전에 `.env`에서 바꿉니다. DB 비밀번호는 데이터 디렉터리가 비어 있을 때 한 번만 적용됩니다.

## 실행

### Docker Compose

데이터베이스마다 서비스와 프로필이 있습니다. 모든 서비스에 프로필이 붙어 있어 프로필 없이 `up`하면 아무것도 뜨지 않습니다. 권장 프로필은 `sqlite`입니다.

| 프로필 | 서비스 | 이미지 | 볼륨 | 역할 |
|---|---|---|---|---|
| `sqlite` | `redmine` | `redmine:7.0.2` | `redmine-files`, `redmine-sqlite` | 컨테이너 하나. 우선 사용 |
| `postgres` | `redmine-postgres`, `postgres` | `redmine:7.0.2`, `postgres:18` | `redmine-postgres-files`, `redmine-postgres-data` | 사용자가 여럿일 때 |
| `mysql` | `redmine-mysql`, `mysql` | `redmine:7.0.2`, `mysql:9.7` | `redmine-mysql-files`, `redmine-mysql-data` | MySQL이 필요할 때 |

DB 포트는 공개하지 않습니다. 앱은 Compose 네트워크의 서비스 이름(`postgres`, `mysql`)으로 접속합니다.

```sh
cd redmine
docker compose --profile sqlite config
docker compose --profile sqlite up -d
docker compose --profile sqlite logs -f redmine
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3080/login
```

세션 키나 DB 비밀번호를 바꾸려면 `example.env`를 참고해 필요한 키만 `.env`에 적습니다. `.env` 값이 `default.env`보다 우선합니다. 매번 `--profile`을 적지 않으려면 `.env`에 `COMPOSE_PROFILES=sqlite`를 넣습니다.

PostgreSQL로 띄울 때는 프로필만 바꿉니다. 비밀번호를 정하려면 `.env`에 `REDMINE_DB_PASSWORD`를 적습니다.

```sh
docker compose --profile postgres config
docker compose --profile postgres up -d
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다. Pod 없이 컨테이너 하나로 SQLite Redmine을 실행합니다. 첨부 파일은 `~/.local/share/redmine/files`, DB 파일은 `~/.local/share/redmine/sqlite`에 둡니다. 디렉터리는 서비스 시작 전에 `ExecStartPre`가 만듭니다. secret은 한 번만 생성하면 재시작해도 유지됩니다.

```sh
cd redmine
openssl rand -hex 64 | tr -d '\n' | podman secret create redmine-secret-key-base -
podman quadlet install redmine.quadlets
systemctl --user daemon-reload
systemctl --user start redmine
```

`podman quadlet install`은 이미 설치된 파일을 덮어쓰지 않습니다. `.quadlets`를 고친 뒤에는 `podman quadlet install --replace redmine.quadlets`, `systemctl --user daemon-reload`, `systemctl --user restart redmine` 순서로 다시 적용합니다. 적용 여부는 `systemctl --user cat redmine`으로 확인합니다.

### podman kube play

PVC `redmine-files`, `redmine-sqlite`가 같은 이름의 Podman 볼륨으로 만들어집니다. 실행 전에 `pod.yaml`의 Secret `SECRET_KEY_BASE`를 바꿉니다. 키를 넣은 `pod.yaml`은 커밋하지 않습니다.

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

컨테이너 이름은 `redmine-redmine`입니다. `podman kube down`은 볼륨을 지우지 않습니다. 데이터까지 지우려면 `podman volume rm redmine-files redmine-sqlite`를 실행합니다.

## 리버스 프록시

`nginx/redmine.conf`와 `caddy/redmine.caddyfile`은 `redmine.example.com`을 `127.0.0.1:3080`으로 넘깁니다. 호스트 이름과 인증서 경로를 실제 값으로 바꿔 씁니다. 웹 UI는 루트 경로(`/`)에서 엽니다. 프로필을 바꿔도 호스트 포트는 같습니다.

| 프록시 | 연결 방법 |
|---|---|
| Nginx | `nginx/redmine.conf`를 프록시의 `conf.d/`에 복사하고 `nginx -t` 후 다시 읽기 |
| Caddy | 프록시 Caddyfile에 `import /path/to/redmine.caddyfile`을 추가하고 `caddy validate --adapter caddyfile --config <Caddyfile>` 후 다시 읽기 |

두 파일은 같은 의미로 다음을 담습니다.

- 업로드 크기: 요청 본문을 100MB까지 허용합니다. Redmine 관리 > 설정 > 파일의 최대 첨부 크기(기본 5MB)를 늘릴 때 이 값보다 작게 둡니다.
- 타임아웃: 큰 업로드와 PDF, Gantt 내보내기를 위해 Nginx는 읽기/쓰기 타임아웃을 300초로 늘립니다. Caddy는 기본 타임아웃이 없습니다.
- `X-Forwarded-Proto`: Rails가 HTTPS 요청으로 인식해 링크와 리디렉션을 `https://`로 만듭니다.

프록시 뒤에서 쓸 때는 관리 > 설정 > 일반의 호스트 이름과 경로, 프로토콜을 실제 주소(`redmine.example.com`, `HTTPS`)로 바꿉니다. 메일 알림 본문의 링크가 이 값을 씁니다. Rails는 사설 대역(127.0.0.1, 10/8, 172.16/12, 192.168/16)에서 온 `X-Forwarded-For`만 믿습니다.

## 백업

SQLite는 DB 파일과 첨부 파일을 함께 복사합니다. Compose 볼륨 이름에는 프로젝트 이름(`redmine_`)이 앞에 붙습니다.

```sh
docker compose --profile sqlite exec redmine cat sqlite/redmine.db > redmine.db
docker run --rm -v redmine_redmine-files:/from:ro -v "$(pwd)":/to docker.io/library/alpine \
  tar -C /from -czf /to/redmine-files.tar.gz .
```

Quadlet의 DB 파일은 `~/.local/share/redmine/sqlite/redmine.db`입니다. `postgres` 프로필은 다음으로 덤프합니다.

```sh
docker compose --profile postgres exec postgres pg_dump -U redmine -Fc redmine > redmine.dump
```

## 주의 사항

- 프로필마다 같은 `127.0.0.1:3080`을 씁니다. 두 프로필을 함께 띄우면 포트가 겹칩니다. 프로필마다 볼륨이 따로 있어 데이터는 옮겨지지 않습니다.
- 이미지 엔트리포인트는 root로 시작해 `files`와 SQLite 디렉터리를 `redmine`(uid 999, gid 999) 소유로 바꾼 뒤 그 사용자로 Rails를 실행합니다. 마운트에 `U`를 붙이면 기동 전에 소유자가 이미지 기본 사용자(root)로 바뀌므로 넣지 않습니다. `CHOWN`, `SETUID`, `SETGID`는 이 전환에 필요해서 남겨 둡니다.
- Quadlet은 `UserNS=keep-id:uid=999,gid=999`와 `User=0`을 함께 씁니다. 999가 호스트 사용자에 매핑되고, 프로세스는 root로 시작해 chown한 뒤 999로 내려갑니다. 그래서 `~/.local/share/redmine` 파일이 호스트 사용자 소유가 됩니다. `keep-id`는 rootless 전용이라 rootful로 실행할 때는 `UserNS=` 줄을 뺍니다. 그 설정 없이 만든 디렉터리는 소유자가 subuid로 남아 있으니 `podman unshare rm -rf ~/.local/share/redmine`로 지우고 다시 초기화합니다.
- `pod.yaml`도 같은 주석(`io.podman.annotations.userns`)과 `runAsUser: 0`, `fsGroup: 999`를 둡니다. rootful에서는 주석 줄을 지웁니다. PVC는 엔진이 SELinux 레이블을 관리합니다.
- SELinux 호스트에서는 Quadlet 바인드 마운트에 `:Z`를 붙입니다. SELinux가 꺼진 호스트에서는 무시됩니다. Compose 이름 있는 볼륨은 엔진이 레이블을 관리하므로 붙이지 않습니다. 그 경로를 호스트 디렉터리로 바꾸면 `:Z`를 붙입니다.
- 메일 발송(SMTP)은 `config/configuration.yml`이 있어야 합니다. 필요하면 예제 파일을 바탕으로 만들어 `/usr/src/redmine/config/configuration.yml`에 읽기 전용으로 마운트합니다. 바인드 마운트는 `:ro,Z`를 붙입니다. 비밀번호가 들어가므로 커밋하지 않습니다.
- 플러그인은 `/usr/src/redmine/plugins`, 테마는 `/usr/src/redmine/public/themes`에 마운트하고 `REDMINE_PLUGINS_MIGRATE=1`을 지정합니다. 바인드 마운트는 `:Z`를 붙입니다. 플러그인이 Redmine 7.0을 지원하는지 먼저 확인합니다.
- 백그라운드 작업은 기본 비동기 어댑터로 앱 프로세스 안에서 처리합니다. 사용자가 많으면 [Sidekiq](https://www.redmine.org/projects/redmine/wiki/SidekiqConfiguration)과 Redis를 따로 둡니다.
- 호스트 포트를 바꾸면 Compose `ports`, Quadlet `PublishPort`, `pod.yaml`의 `hostPort`, 프록시 업스트림을 함께 수정합니다.
- 상태 확인은 로그인 페이지 `http://localhost:3000/login`을 이미지에 들어 있는 `wget`으로 요청합니다. 첫 실행은 마이그레이션 시간 때문에 시작 유예를 120초로 둡니다.
- 재시작 정책은 Compose `unless-stopped`, Pod `Always`, Quadlet `Restart=on-failure`입니다. Quadlet은 상태 확인이 실패하면 컨테이너를 종료해 다시 시작합니다.
- 이미지는 `docker.io/library/redmine:7.0.2`(Debian, uid/gid 999)입니다. `7.0.2-alpine`은 그룹 id가 1000이라 `UserNS=`의 gid와 맞지 않습니다. 태그를 바꿀 때는 Compose, Quadlet, `pod.yaml`을 함께 바꿉니다. Redmine 버전을 올리면 시작할 때 `db:migrate`가 실행됩니다. PostgreSQL 메이저 버전을 올릴 때는 `pg_dump`와 복원이 필요합니다.

## 참고 자료

- [Redmine 공식 이미지](https://hub.docker.com/_/redmine)
- [docker-library/redmine](https://github.com/docker-library/redmine)
- [Redmine 설치 문서](https://www.redmine.org/projects/redmine/wiki/RedmineInstall)
- [Redmine 백업과 복원](https://www.redmine.org/projects/redmine/wiki/RedmineBackupRestore)
- [PostgreSQL 공식 이미지](https://hub.docker.com/_/postgres)
- [MySQL 공식 이미지](https://hub.docker.com/_/mysql)
- [Compose 프로필](https://docs.docker.com/compose/how-tos/profiles/)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
