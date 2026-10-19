# mysql

공식 [MySQL](https://hub.docker.com/_/mysql) 이미지를 로컬에서 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

권장 실행은 컨테이너 하나입니다. Quadlet과 `pod.yaml`은 LTS `9.7`만 정의합니다. Compose는 같은 포트를 쓰는 버전을 프로필로 나누며, 프로필 없이 `up`하면 아무것도 뜨지 않습니다.

데이터베이스는 `127.0.0.1:3306`에서만 열립니다. 기본 데이터베이스와 사용자는 `app`이고, 관리자는 `root`입니다. TCP 서비스라 `nginx/`, `caddy/` 프록시 설정은 두지 않습니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose (프로필 `9.7`, `8.4`, `26`) |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `example.env` | `.env`에 적을 키와 예시 |
| `mysql.quadlets` | Podman Quadlet (컨테이너 하나, MySQL 9.7) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap, Secret (MySQL 9.7) |

## 비밀번호

저장소에 있는 기본 비밀번호(`mysql`)는 예제 값이므로 실행 전에 직접 생성한 값으로 바꿉니다. `MYSQL_USER`는 `root`로 둘 수 없습니다.

```sh
openssl rand -hex 32
```

| 실행 방식 | 비밀번호 전달 방법 |
|---|---|
| Compose | `example.env`를 `.env`로 복사한 뒤 `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD` 입력 |
| Quadlet | podman secret `mysql-root-password`, `mysql-password`를 미리 생성 |
| kube play | `pod.yaml`의 Secret 값을 교체 |

`MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_USER`는 데이터 디렉터리가 비어 있을 때 한 번만 적용됩니다. 이후 비밀번호를 바꾸려면 `ALTER USER`를 실행하거나 데이터를 지우고 다시 초기화합니다.

## 실행

### Docker Compose

주 버전마다 서비스와 프로필이 하나씩 있습니다. 모든 서비스에 프로필이 붙어 있어 프로필 없이 `up`하면 아무것도 뜨지 않습니다. 권장 프로필은 LTS `9.7`입니다.

| 프로필 | 서비스 | 이미지 | 볼륨 | 역할 |
|---|---|---|---|---|
| `9.7` | `mysql-9.7` | `mysql:9.7` | `mysql-9.7-data` | 현재 LTS. 우선 사용 |
| `8.4` | `mysql-8.4` | `mysql:8.4` | `mysql-8.4-data` | 이전 LTS |
| `26` | `mysql-26` | `mysql:26` | `mysql-26-data` | innovation. `latest`와 같은 라인 |

```sh
cd mysql
cp example.env .env # 비밀번호 입력
docker compose --profile 9.7 config
docker compose --profile 9.7 up -d
docker compose --profile 9.7 down
```

매번 `--profile`을 적지 않으려면 `.env`에 `COMPOSE_PROFILES=9.7`을 넣습니다. `.env`의 빈 값도 `default.env` 값을 덮어쓰므로 바꿀 키만 남깁니다.

접속 확인은 다음과 같습니다.

```sh
docker compose --profile 9.7 exec mysql-9.7 sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT VERSION();"'
```

호스트에서 접속할 때는 `mysql -h 127.0.0.1 -P 3306 -uapp -p app`를 사용합니다. 발행 포트로 들어온 접속은 컨테이너 안의 `localhost`가 아니므로 `root@localhost` 소켓 계정으로는 붙지 않습니다. `root`로 TCP 접속이 필요하면 `-uroot`와 `MYSQL_ROOT_PASSWORD`를 사용합니다. 엔트리포인트는 `root@'%'`도 만듭니다.

초기 SQL은 `/docker-entrypoint-initdb.d`에, 서버 설정은 `/etc/mysql/conf.d`에 넣습니다. 디렉터리를 바인드 마운트할 때는 SELinux 호스트에서 `:ro,Z`를 붙입니다. 이 파일은 데이터 디렉터리가 비어 있는 첫 기동에서만 실행됩니다.

### Podman Quadlet

Podman 5.6 이상이 필요합니다. Pod 없이 컨테이너 하나로 MySQL 9.7을 실행하며, 데이터는 `~/.local/share/mysql`에 저장합니다. 디렉터리는 서비스 시작 전에 `ExecStartPre`가 만듭니다. secret은 한 번만 생성하면 재시작해도 유지됩니다.

```sh
# /run은 root만 쓸 수 있으므로 소켓 디렉터리를 한 번 만든다. 재부팅해도 다시 만든다
# 호스트 클라이언트 기본 경로는 /var/lib/mysql/mysql.sock 이라 그 이름으로 링크한다
sudo tee /etc/tmpfiles.d/mysql.conf >/dev/null <<EOF
d /run/mysqld 0700 $(id -un) $(id -gn) -
d /var/lib/mysql - - - -
L /var/lib/mysql/mysql.sock - - - - /run/mysqld/mysqld.sock
EOF
sudo systemd-tmpfiles --create /etc/tmpfiles.d/mysql.conf
cd mysql
openssl rand -hex 32 | tr -d '\n' | podman secret create mysql-root-password -
openssl rand -hex 32 | tr -d '\n' | podman secret create mysql-password -
podman quadlet install mysql.quadlets
systemctl --user daemon-reload
systemctl --user start mysql
```

`podman quadlet install`은 이미 설치된 파일을 덮어쓰지 않습니다. `.quadlets`를 고친 뒤에는 `podman quadlet install --replace mysql.quadlets`, `systemctl --user daemon-reload`, `systemctl --user restart mysql` 순서로 다시 적용합니다. 적용 여부는 `systemctl --user cat mysql`으로 확인합니다.

비밀번호 확인은 다음과 같습니다.

```sh
podman secret inspect --showsecret --format '{{.SecretData}}' mysql-root-password
```

서버 소켓은 `/run/mysqld/mysqld.sock`이고, `/var/lib/mysql/mysql.sock`이 그 파일을 가리킵니다. Oracle Linux와 RHEL 계열 클라이언트의 기본 경로가 이쪽이라 추가 옵션 없이 접속합니다. 소켓 접속도 `caching_sha2_password`라 비밀번호가 필요합니다. 소켓에서 쓰는 계정은 `root`@`localhost`입니다.

```sh
mysql -uroot -p
```

`app` 계정은 `app`@`%`로 만들어집니다. TCP로 접속합니다.

```sh
mysql -h 127.0.0.1 -uapp -p app
```

sudo를 쓸 수 없으면 `mysql.quadlets`의 주석대로 `Volume=%t/mysql:/var/run/mysqld:Z`와 `RuntimeDirectory=mysql`, `RuntimeDirectoryMode=0700`을 켜고 `/run/mysqld` 줄을 지웁니다. systemd가 서비스 시작 전에 `/run/user/<UID>/mysql`을 만들고 멈출 때 지웁니다. 접속은 `mysql --socket="$XDG_RUNTIME_DIR/mysql/mysqld.sock" -uroot -p`입니다.

다른 주 버전을 쓰려면 `Image=` 태그를 바꾸고 데이터 디렉터리도 나눕니다. 기존 데이터 디렉터리는 다른 주 버전으로 그대로 열 수 없습니다.

rootful로 실행할 때는 `UserNS=` 줄을 빼고 tmpfiles 소유자를 컨테이너 mysql과 같은 `999 999`로 바꿉니다. `%h`가 `/root`이므로 데이터는 `/root/.local/share/mysql`에 저장됩니다.

### podman kube play

`pod.yaml`의 `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD` 값을 교체한 뒤 실행합니다. 비밀번호를 넣은 `pod.yaml`은 커밋하지 않습니다.

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

## 주의 사항

- 프로필마다 같은 `127.0.0.1:3306`을 씁니다. 두 버전을 함께 띄우려면 한쪽 호스트 포트를 바꿉니다. Quadlet과 kube play도 같은 포트를 씁니다.
- 주 버전마다 볼륨이 따로 있습니다. 버전을 올려도 데이터는 옮겨지지 않으며 `mysqldump`로 옮깁니다. innovation(`26`)은 태그가 자주 움직이므로 이미지를 새로 받기 전에 덤프합니다.
- 공식 이미지의 계정 플러그인은 `caching_sha2_password`입니다. 클라이언트도 이 플러그인을 지원해야 합니다.
- X Protocol `33060`은 컨테이너 안에만 있습니다. 호스트에서 쓰려면 Compose 포트, Quadlet `PublishPort`, `pod.yaml`의 `hostPort`를 함께 추가합니다.
- 이미지 엔트리포인트는 root로 시작해 `/var/lib/mysql`과 소켓 디렉터리를 `mysql`(uid 999, gid 999) 소유로 바꾼 뒤 그 사용자로 `mysqld`를 실행합니다. 마운트에 `U`를 붙이면 기동 전에 소유자가 이미지 기본 사용자(root)로 바뀌므로 넣지 않습니다. `CHOWN`, `SETUID`, `SETGID`는 이 전환에 필요해서 남겨 둡니다.
- Quadlet은 `UserNS=keep-id:uid=999,gid=999`로 컨테이너의 `mysql`을 호스트 사용자에 매핑합니다. 데이터와 소켓 파일이 호스트 사용자 소유가 되어 `podman unshare` 없이 백업하거나 지울 수 있습니다. `keep-id`는 rootless 전용이라 rootful로 실행할 때는 `UserNS=` 줄을 뺍니다. 이 설정 없이 만든 `~/.local/share/mysql`는 소유자가 subuid로 남아 있으니 `podman unshare rm -rf ~/.local/share/mysql`로 지우고 다시 초기화합니다.
- 소켓 디렉터리 `/run/mysqld`는 `/etc/tmpfiles.d/mysql.conf`가 호스트 사용자 소유 `0700`으로 만듭니다. 같은 파일이 `/var/lib/mysql/mysql.sock` 링크도 만듭니다. `/run`은 재부팅하면 비워지지만 `systemd-tmpfiles`가 부팅할 때마다 다시 만들므로 따로 할 일은 없습니다. 디렉터리가 없으면 컨테이너가 `statfs ... no such file or directory`로 시작하지 않습니다. 링크가 없으면 클라이언트는 `Can't connect ... socket '/var/lib/mysql/mysql.sock'`로 실패합니다.
- 호스트에 MySQL이나 MariaDB 패키지가 설치되어 있으면 `/var/lib/mysql`, `/run/mysqld`, 3306 포트가 겹칩니다. 이미 데이터 디렉터리인 `/var/lib/mysql`에는 링크를 만들지 않고 `--socket=/run/mysqld/mysqld.sock`으로 접속합니다. Compose와 kube play는 소켓을 공유하지 않습니다.
- SELinux 호스트에서는 Quadlet 바인드 마운트에 `:Z`를 붙입니다. SELinux가 꺼진 호스트에서는 무시됩니다. Compose 이름 있는 볼륨과 kube play PVC는 엔진이 레이블을 관리하므로 붙이지 않습니다. 데이터 경로를 호스트 디렉터리로 바꾸면 Compose와 Quadlet 모두 `:Z`를 붙입니다.
- 상태 확인은 `mysqladmin ping -h 127.0.0.1 --silent`입니다. 서버가 접속을 거부해도 프로세스가 살아 있으면 성공으로 나옵니다. 초기화 중 임시 서버는 `--skip-networking`이라 이 TCP 확인은 본 서버가 포트를 연 뒤에만 성공합니다. Quadlet은 상태 확인이 실패하면 컨테이너를 종료해 다시 시작합니다.
- 이미지는 마이너 태그(`mysql:9.7` 등)로 고정되어 있습니다. 패치까지 고정하려면 태그를 `9.7.2`처럼 바꾸고 Compose, Quadlet, `pod.yaml`을 같이 맞춥니다. `latest`는 innovation 라인을 가리키므로 쓰지 않습니다.

## 참고 자료

- [MySQL Docker 공식 이미지](https://hub.docker.com/_/mysql)
- [Compose 프로필](https://docs.docker.com/compose/how-tos/profiles/)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
