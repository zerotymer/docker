# gitea

[Gitea](https://about.gitea.com/) Git 서비스를 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

웹 UI는 `13000`, Git SSH는 `2222` 포트로 모든 인터페이스에 열립니다. 외부 공개는 리버스 프록시(예: `nginx/`)를 앞에 둡니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yml` | Docker Compose / podman-compose |
| `default.env`, `.env.example` | Compose 환경 변수 (`.env`가 우선) |
| `gitea.quadlets` | Podman Quadlet (Pod, 볼륨, 컨테이너) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap |
| `../gitea-runner/` | Gitea Actions runner. 사용법은 [gitea-runner/README.md](../gitea-runner/README.md) |

## 설정 방식

모든 실행 방식에서 `TZ`, `USER_UID`, `USER_GID`만 지정합니다. 서버 설정은 첫 접속 때 설치 마법사에서 입력하며 `/data/gitea/conf/app.ini`에 저장됩니다. `SECRET_KEY`도 마법사가 생성해 `app.ini`에 저장합니다.

설치 마법사는 처음 접속한 사람이 진행할 수 있으므로, 컨테이너를 띄운 직후 바로 마법사를 마칩니다. 마법사에서 관리자 계정을 함께 만들 수 있습니다.

`GITEA__섹션__키` 형식의 환경 변수를 추가하면 컨테이너가 시작될 때마다 `app.ini`의 해당 항목을 덮어씁니다.

### 설치 마법사 입력값

| 항목 | 입력값 |
|---|---|
| 데이터베이스 유형 | SQLite3 (이미지 기본값) |
| 서버 도메인 | 접속에 쓰는 도메인 (예: `gitea.example.com`) |
| SSH 서버 포트 | `2222` (호스트에 공개한 포트) |
| Gitea 기본 URL (`ROOT_URL`) | runner와 job 컨테이너가 접근할 수 있는 주소 (예: `https://gitea.example.com/`) |

`ROOT_URL`은 사용자가 접속하는 주소이면서 Actions job 컨테이너가 저장소를 checkout하는 주소이므로 `localhost`, `127.0.0.1`은 쓰지 않습니다. 바꾸면 runner의 `GITEA_INSTANCE_URL`도 같은 주소로 맞춥니다.

## 실행

### Docker Compose

데이터는 `./.data`에 저장되며 이전 구성(`docker-compose.yml`)과 같은 경로, 포트, 컨테이너 이름을 사용합니다.

```sh
cd gitea
docker compose config
docker compose up -d
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다.

```sh
podman quadlet install gitea.quadlets
systemctl --user daemon-reload
systemctl --user start gitea
```

rootless Podman은 기본적으로 1024 미만 포트를 열 수 없으므로 SSH를 `2222`로 공개합니다.

### podman kube play

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

실행 후 `http://<호스트>:13000/`에서 설치 마법사를 진행합니다.

## 주의 사항

- 저장소, SQLite DB, `app.ini`, SSH 호스트 키는 모두 `/data`에 저장됩니다(Compose `./.data`, Podman `gitea-vol`). 지우면 모든 저장소가 함께 사라집니다.
- SELinux 호스트에서는 바인드 마운트한 데이터 디렉터리를 컨테이너가 읽을 수 있도록 `:Z`로 레이블을 바꿉니다. 없으면 `sshd`가 `/data/ssh`의 호스트 키를 읽지 못해(`container_t` → `var_t` 등 `denied { read }`) Git SSH가 동작하지 않습니다. Podman named volume(`gitea-vol`)은 자동으로 레이블이 붙지만, 데이터를 `cp -a` 등으로 레이블째 복사했거나 Quadlet `Volume=`을 호스트 경로로 바꿨다면 `:Z`를 붙입니다. SELinux가 꺼진 호스트에서는 `:Z`가 무시됩니다.
- `app.ini`의 `SECRET_KEY`는 2FA 시크릿 같은 DB 내 암호화 데이터에 쓰이므로 데이터를 옮길 때 `app.ini`도 함께 옮깁니다.
- 리버스 프록시가 같은 호스트에서 직접 실행된다면 웹 포트를 `127.0.0.1:13000:3000`으로 좁힐 수 있습니다. 프록시가 컨테이너로 실행되거나 다른 호스트에 있다면 그대로 둡니다.
- 시간대는 `/etc/localtime` 마운트 대신 `TZ`로 지정합니다. Gitea 바이너리에 tzdata가 포함되어 있습니다.
- 상태 확인은 `http://localhost:3000/api/healthz` 엔드포인트를 사용합니다.
- 이미지는 `docker.gitea.com/gitea:1.26.1`로 고정되어 있습니다. 갱신 전에는 데이터를 백업하고 릴리스 노트의 마이그레이션 항목을 확인합니다.

## 참고 자료

- [Gitea Docker 설치](https://docs.gitea.com/installation/install-with-docker)
- [환경 변수로 app.ini 구성](https://docs.gitea.com/installation/install-with-docker#managing-deployments-with-environment-variables)
- [설정 항목](https://docs.gitea.com/administration/config-cheat-sheet)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
