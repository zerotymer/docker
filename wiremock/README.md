# wiremock

[WireMock](https://wiremock.org/) 스텁 서버를 로컬에서 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

HTTP와 관리 API는 `127.0.0.1:8080`에서만 열리며, `http://127.0.0.1:8080/`로 접속합니다. 이전 Compose는 `8080`을 모든 인터페이스에 공개했습니다. 다른 호스트에서 호출하려면 앞단에 리버스 프록시를 두거나, 포트 바인딩의 `127.0.0.1:`을 제거합니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `wiremock.quadlets` | Podman Quadlet (컨테이너) |
| `pod.yaml` | `podman kube play`용 Pod, ConfigMap |
| `data/mappings/` | 스텁 매핑 JSON |
| `data/__files/` | 응답 본문 파일 |

## 스텁

WireMock은 `/home/wiremock/mappings`의 JSON과 `/home/wiremock/__files`의 본문 파일을 읽습니다. 저장소 디렉터리 이름이 `mapping`이면 매핑이 로드되지 않으므로 `data/mappings`로 둡니다.

| 요청 | 응답 |
|---|---|
| `GET /api/users/1` | JSON `{"id":1,"name":"Kim"}` |
| `GET /api/IFX1001` | `__files/IFX1001.xml` |
| `GET /api/order/1` | `__files/order.xml` (파일 없음) |

`WIREMOCK_OPTIONS`는 모든 스텁에 응답 템플릿을 적용하고(`--global-response-templating`), 요청 기록을 1000건까지만 유지하며(`--max-request-journal=1000`), 시작 배너를 생략합니다(`--disable-banner`). JVM 힙은 `JAVA_OPTS=-Xmx256m`으로 제한합니다. 값을 바꾸면 `default.env`, `wiremock.quadlets`의 `Environment=`, `pod.yaml` ConfigMap `wiremock-default`를 함께 수정합니다.

매핑 파일을 고친 뒤에는 컨테이너를 다시 시작하거나 `POST /__admin/mappings/reset`으로 다시 읽힙니다.

## 실행

### Docker Compose

데이터는 `./data`를 그대로 마운트합니다. 프로젝트 이름은 디렉터리 이름(`wiremock`)을 따릅니다.

```sh
cd wiremock
docker compose config
docker compose up -d
```

기본값을 바꾸려면 `.env`를 만들어 필요한 변수만 적습니다. `.env` 값이 `default.env`보다 우선합니다.

확인:

```sh
curl -fsS http://127.0.0.1:8080/__admin/health
curl -fsS http://127.0.0.1:8080/api/users/1
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다. `podman quadlet install`은 유닛을 홈 디렉터리로 복사하므로, 저장소 `data/`를 가리키는 링크를 먼저 만듭니다.

```sh
cd wiremock
mkdir -p ~/.local/share
ln -sfn "$(pwd)/data" ~/.local/share/wiremock
podman quadlet install wiremock.quadlets
systemctl --user daemon-reload
systemctl --user start wiremock
```

저장소를 다른 경로로 옮기면 링크를 다시 만듭니다.

### podman kube play

스텁은 `pod.yaml`의 ConfigMap `wiremock-mappings`, `wiremock-files`에 들어 있습니다. `data/mappings`, `data/__files`를 수정하면 이 ConfigMap도 같은 내용으로 맞춥니다. ConfigMap은 읽기 전용이라 관리 API로 추가한 매핑은 컨테이너가 지워지면 사라집니다.

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

## 주의 사항

- 관리 API(`/__admin`)는 인증이 없습니다. 포트를 모든 인터페이스에 열면 스텁을 바꾸거나 요청 기록을 볼 수 있습니다. 외부 공개는 리버스 프록시에서 관리 경로를 막은 뒤에 합니다.
- 같은 호스트의 `termix`도 `127.0.0.1:8080`을 사용합니다. 함께 실행하려면 한쪽 호스트 포트를 바꿉니다.
- Compose와 Quadlet은 `data/` 전체를 `/home/wiremock`에 읽기 전용으로 마운트합니다. 디렉터리 안에 `mappings`와 `__files`가 있어야 합니다. 관리 API로 추가한 스텁은 메모리에만 남고 컨테이너를 다시 시작하면 사라집니다.
- Quadlet은 마운트에 `U`를 붙여 Podman이 `data/` 소유권을 컨테이너 사용자에 맞춥니다. 링크를 따라 저장소 `data/`의 소유자가 바뀔 수 있습니다. Docker는 `U`를 지원하지 않아 Compose에는 넣지 않았습니다. 소유권이 어긋나면 `podman unshare chown -R 0:0 data`로 되돌립니다.
- 재시작 정책은 실패 시에만 다시 시작합니다(Quadlet `Restart=on-failure`, Compose `on-failure`, Pod `OnFailure`). Quadlet은 상태 확인이 실패하면 컨테이너를 종료해 다시 시작합니다. Compose는 상태 확인 실패만으로 다시 시작하지 않습니다.
- `GET /api/order/1` 매핑은 `__files/order.xml`을 가리키는데 그 파일은 저장소에 없습니다. 호출하면 본문 파일을 찾지 못합니다.
- 이미지는 기본으로 root로 실행됩니다. 마운트가 읽기 전용이므로 엔트리포인트의 `uid` 환경 변수(소유권 변경)는 쓰지 않습니다.
- SELinux 호스트에서는 바인드 마운트에 `:Z`를 붙입니다. SELinux가 꺼진 호스트에서는 `:Z`가 무시됩니다.
- 상태 확인은 `http://localhost:8080/__admin/health`를 사용합니다. 이 경로는 WireMock 3.1.0부터 있습니다.
- 이미지는 `docker.io/wiremock/wiremock:latest`를 씁니다. 다시 받을 때마다 버전이 바뀔 수 있으니, 재현이 필요하면 세 파일의 태그를 같은 버전으로 고정합니다.

## 참고 자료

- [WireMock Docker](https://wiremock.org/docs/standalone/docker/)
- [WireMock 이미지](https://hub.docker.com/r/wiremock/wiremock)
- [응답 템플릿](https://wiremock.org/docs/response-templating/)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
