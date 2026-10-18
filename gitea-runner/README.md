# gitea-runner

Gitea Actions 작업을 실행하는 [act_runner](https://gitea.com/gitea/runner) 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

runner는 컨테이너 엔진 소켓으로 job 컨테이너를 만듭니다. 공개 포트는 없습니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yml` | Docker Compose / podman-compose |
| `default.env`, `.env.example` | Compose 환경 변수 (`.env`가 우선) |
| `config.yml` | runner 설정. 비어 있으면 모든 항목이 기본값 |
| `gitea-runner.quadlets` | Podman Quadlet (Pod, 볼륨, 컨테이너) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap, Secret |

## 이미지 버전

이미지는 `docker.io/gitea/act_runner:0.6.1`로 고정합니다. `gitea/act_runner:latest`는 2026-04-30에 0.6.1로 갱신된 뒤 더 이상 갱신되지 않으며, 둘은 같은 이미지(digest)입니다.

프로젝트는 이후 `gitea/runner`로 이름이 바뀌었고 v5.0.0에 호환성 변경이 있습니다(바이너리 이름 `gitea-runner`, `runs-on` 필수, 설정 값의 `${NAME}` 확장, 기존 `GITEA_RUNNER_*` 설정용 환경 변수 제거 등). 지금 구성과 workflow를 그대로 유지하기 위해 0.6.1을 사용하며, 올릴 때는 [릴리스 노트](https://gitea.com/gitea/runner/releases)를 확인하고 이미지를 `docker.io/gitea/runner:<버전>`으로 바꿉니다.

## Gitea 주소

`GITEA_INSTANCE_URL`은 Gitea의 `ROOT_URL`과 같은 주소로 지정하고 `localhost`나 `127.0.0.1`은 쓰지 않습니다. 컨테이너 안에서 `localhost`는 runner 자신을 가리킵니다. job 컨테이너도 checkout할 때 `ROOT_URL`로 접속하므로 이 주소는 job 컨테이너에서도 접근할 수 있어야 합니다.

## 등록

첫 실행 때 `GITEA_RUNNER_REGISTRATION_TOKEN`으로 Gitea에 등록하고 결과를 데이터 디렉터리의 `.runner`에 저장합니다. `.runner`가 있으면 등록을 건너뛰므로, 등록 토큰과 `GITEA_RUNNER_NAME`, `GITEA_RUNNER_LABELS`는 처음 등록할 때만 사용됩니다. 토큰은 Gitea의 사이트 관리 > Actions > Runners에서 발급합니다.

| 실행 방식 | 토큰 전달 방법 | 등록 정보 위치 |
|---|---|---|
| Compose | `.env`의 `GITEA_RUNNER_REGISTRATION_TOKEN` | `./.data/.runner` |
| Quadlet | podman secret `gitea-runner-token` | `gitea-runner-vol` 볼륨 |
| kube play | `pod.yaml`의 Secret `GITEA_RUNNER_REGISTRATION_TOKEN` | `gitea-runner-vol` PVC |

다시 등록하려면 `.runner`를 지우고 재시작합니다. 이때 Gitea에 이전 runner가 오프라인으로 남으므로 UI에서 삭제합니다.

## 컨테이너 엔진 호환성

act_runner는 Docker API를 사용합니다. Podman은 `podman.socket`이 제공하는 Docker 호환 API로 동작합니다. 공식 이미지는 Docker 기준으로 만들어졌으므로 Podman 구성은 아래 조건을 맞춰야 합니다.

| 항목 | Docker | Podman (rootless) |
|---|---|---|
| 소켓 | `/var/run/docker.sock` | `/run/user/<UID>/podman/podman.sock` (`systemctl --user enable --now podman.socket` 필요) |
| 소켓 마운트 | 호스트와 같은 경로 | 호스트와 같은 경로 + `DOCKER_HOST` 지정 |
| SELinux | 해당 없음 | 소켓 접근을 위해 라벨 비활성화 (`SecurityLabelDisable=true`, `spc_t`) |
| job 이미지 이름 | 짧은 이름 가능 | 레지스트리를 포함한 전체 이름 권장 (`docker.io/...`) |

job 컨테이너에는 기본적으로 엔진 소켓이 같은 경로로 전달됩니다(`container.docker_host: ""`). act_runner는 runner 컨테이너 안에서 보이는 소켓 경로를 그대로 호스트 경로로 사용하므로, 경로가 다르면 Podman에서 job 컨테이너를 만들지 못합니다. 그래서 모든 구성에서 소켓을 호스트와 같은 경로에 마운트하고 `DOCKER_HOST`로 그 경로를 지정합니다. Docker에서는 이전 구성(`/var/run/docker.sock:/var/run/docker.sock`)과 동일합니다.

job에서 `docker` 명령이 필요 없다면 `config.yml`에 다음을 넣어 소켓 전달을 끕니다. 엔진 소켓은 호스트(rootless Podman이면 해당 사용자) 권한과 같으므로 신뢰하지 않는 저장소의 workflow를 실행할 때는 끄는 편이 안전합니다.

```yaml
container:
  docker_host: "-"
```

## 실행

### Docker Compose

```sh
cd gitea-runner
cp .env.example .env # GITEA_INSTANCE_URL, GITEA_RUNNER_REGISTRATION_TOKEN 입력
docker compose config
docker compose up -d
docker compose logs -f
```

설정 파일은 항상 컨테이너의 `/config.yaml`로 마운트하고 `CONFIG_FILE`도 Compose에서 이 경로로 고정합니다. `.env`의 `CONFIG_FILE` 값은 무시됩니다.

podman-compose에서 rootless Podman을 쓸 때는 `.env`에 `DOCKER_SOCK=/run/user/<UID>/podman/podman.sock`을 추가하고, SELinux 호스트라면 `security_opt`에 `label=disable`을 추가합니다.

### Podman Quadlet

Podman 5.6 이상이 필요합니다. `gitea-runner.quadlets`의 `GITEA_INSTANCE_URL`을 수정하고 소켓과 secret을 준비합니다.

```sh
systemctl --user enable --now podman.socket
printf '%s' '<등록 토큰>' | podman secret create gitea-runner-token -
podman quadlet install gitea-runner.quadlets
systemctl --user daemon-reload
systemctl --user start gitea-runner
```

`systemctl --user`는 그 사용자의 systemd 세션이 있어야 동작합니다. `su`나 `sudo -u`로 전환한 셸에는 세션이 없어서 `$DBUS_SESSION_BUS_ADDRESS and $XDG_RUNTIME_DIR not defined` 오류가 납니다. 전용 계정(예: `gitea-runner`)으로 실행할 때는 관리자 계정에서 linger를 켜고 세션에 연결합니다. linger가 없으면 로그아웃할 때 runner도 종료됩니다.

```sh
# 관리자 계정
sudo loginctl enable-linger gitea-runner
sudo machinectl shell gitea-runner@ # systemd-container 패키지 필요

# machinectl이 없으면 전환한 셸에서 직접 지정
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
```

`%t`는 rootless에서 `/run/user/<UID>`, rootful에서 `/run`으로 바뀌므로 Quadlet 파일은 두 경우 모두 그대로 사용할 수 있습니다.

### podman kube play

`pod.yaml`의 `GITEA_INSTANCE_URL`과 Secret `GITEA_RUNNER_REGISTRATION_TOKEN`을 교체한 뒤 실행합니다. 소켓 경로는 UID 1000 기준이므로 다른 사용자라면 `DOCKER_HOST`와 `podman-sock` 경로를 함께 바꿉니다. 토큰을 넣은 `pod.yaml`은 커밋하지 않습니다.

```sh
systemctl --user enable --now podman.socket
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

## 주의 사항

- `config.yml`이 비어 있으면 레이블은 `.runner`에 저장된 값을, 나머지는 기본값을 사용합니다. 전체 옵션은 `docker compose run --rm --entrypoint act_runner runner generate-config`로 확인합니다.
- `actions/cache`용 캐시 서버는 runner 컨테이너 안에서 임의 포트로 열립니다. job 네트워크에서 runner로 접근할 수 없어 캐시가 실패하면 `config.yml`의 `container.network`를 지정하거나 `cache.enabled: false`로 끕니다.
- 저장소에 커밋된 `.env`에는 토큰이 포함될 수 있습니다. 실제 토큰이 들어갔다면 Gitea에서 재발급하고 `.env`는 추적에서 제외합니다.

## 참고 자료

- [Gitea Actions 빠른 시작](https://docs.gitea.com/usage/actions/quickstart)
- [act_runner 설치](https://docs.gitea.com/usage/actions/act-runner)
- [gitea/runner](https://gitea.com/gitea/runner)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
