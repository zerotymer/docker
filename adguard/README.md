# adguard

[AdGuard Home](https://adguard.com/adguard-home/overview.html) 네트워크 단위 광고·추적 차단 DNS 서버를 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

다른 기기가 DNS 서버로 사용해야 하므로 다른 스택과 달리 모든 인터페이스에 포트를 공개합니다. 최초 실행 후 같은 호스트에서 `http://127.0.0.1:3000/`으로 설정 마법사를 진행합니다. 리버스 프록시를 앞에 둘 때는 [리버스 프록시](#리버스-프록시)를 참고합니다.

이 디렉터리의 파일은 기본 구성입니다. 포트, 공개 범위, 프록시 사용 여부는 각 서버에서 이 파일을 바탕으로 고칩니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `adguard.quadlets` | Podman Quadlet (컨테이너) |
| `pod.yaml` | `podman kube play`용 Pod, ConfigMap, PVC |
| `nginx/adguard.conf` | Nginx `server` 블록 |
| `caddy/adguard.caddyfile` | Caddy 사이트 블록 |
| `data/` | Compose 실행 데이터 (`work`, `conf`). 커밋하지 않음 |

## 포트

| 호스트 | 컨테이너 | 용도 |
|---|---|---|
| `53/tcp`, `53/udp` | `53` | 일반 DNS |
| `80/tcp` | `80` | 웹 UI, 평문 DNS-over-HTTPS (리버스 프록시 업스트림) |
| `443/tcp`, `443/udp` | `443` | AdGuard Home 자체 HTTPS 웹 UI, DNS-over-HTTPS (HTTP/3 포함) |
| `127.0.0.1:3000/tcp` | `3000` | 최초 설정 마법사 |
| `853/tcp` | `853` | DNS-over-TLS |
| `853/udp` | `853` | DNS-over-QUIC |
| `5443/tcp`, `5443/udp` | `5443` | DNSCrypt |

설정 마법사에서 웹 UI 포트는 기본값 `80`, DNS 포트는 `53`으로 둡니다. 다른 값을 고르면 포트 매핑과 프록시 업스트림도 함께 바꿉니다. 마법사를 마치면 웹 UI는 80번으로 옮겨가고 3000번은 더 이상 쓰이지 않습니다. 443(HTTPS, DoH), 853(DoT, DoQ), 5443(DNSCrypt)은 AdGuard Home의 **설정 → 암호화 설정**에 인증서를 등록해야 동작하며, 쓰지 않으면 해당 포트는 지워도 됩니다. 리버스 프록시가 TLS를 맡는 서버에서는 443을 프록시가 쓰므로 AdGuard Home의 443 매핑을 지웁니다. DNS-over-QUIC의 구버전 포트(`784`, `8853`)는 `AdGuardHome.yaml`의 `port_dns_over_quic`를 바꾼 경우에만 매핑을 추가합니다.

같은 호스트에서 `heimdall`이나 리버스 프록시(80, 443), `grafana`, `wiki.js`, `llm-registry`(3000)를 함께 실행하면 포트가 충돌합니다. 한쪽의 호스트 포트를 바꿉니다.

## 사전 준비

### systemd-resolved 충돌

Ubuntu 등 systemd-resolved를 쓰는 호스트는 `127.0.0.53:53`을 이미 사용하므로 53번 포트 바인딩이 실패합니다. 스텁 리스너를 끄고 호스트 DNS를 다시 연결합니다.

```sh
sudo mkdir -p /etc/systemd/resolved.conf.d
printf '[Resolve]\nDNS=127.0.0.1\nDNSStubListener=no\n' | sudo tee /etc/systemd/resolved.conf.d/adguardhome.conf
sudo ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
sudo systemctl reload-or-restart systemd-resolved
```

이 설정 후에는 호스트도 AdGuard Home으로 이름을 조회하므로, 컨테이너가 떠 있지 않으면 이미지를 받을 수 없습니다. 위 명령보다 먼저 `docker compose pull` 또는 `podman pull docker.io/adguard/adguardhome:latest`로 이미지를 받아 둡니다.

### rootless Podman의 낮은 포트

rootless Podman은 기본적으로 1024 미만 포트(53, 80, 443, 853)를 열 수 없습니다. 비특권 포트 시작값을 낮추거나 rootful로 실행합니다.

```sh
echo 'net.ipv4.ip_unprivileged_port_start=53' | sudo tee /etc/sysctl.d/90-unprivileged-port.conf
sudo sysctl --system
```

## 실행

### Docker Compose

데이터는 `./data/work`, `./data/conf`에 바인드 마운트합니다. Podman은 없는 원본 디렉터리를 만들지 않으므로 먼저 만들어 둡니다.

```sh
cd adguard
mkdir -p data/work data/conf
docker compose config
docker compose up -d
```

기본값을 바꾸려면 `.env`를 만들어 필요한 변수만 적습니다. `.env` 값이 `default.env`보다 우선합니다.

### Podman Quadlet

Podman 5.6 이상이 필요합니다. Pod 없이 컨테이너 하나로 실행하며, 데이터는 `~/.local/share/adguard/{work,conf}`에 저장합니다. 디렉터리는 서비스 시작 전에 `ExecStartPre`가 만듭니다.

```sh
podman quadlet install adguard.quadlets
systemctl --user daemon-reload
systemctl --user start adguard
```

rootful로 실행할 때는 `sudo podman quadlet install adguard.quadlets` 후 `sudo systemctl daemon-reload`, `sudo systemctl start adguard`을 사용합니다. 이때 `%h`는 `/root`이므로 데이터는 `/root/.local/share/adguard`에 저장됩니다.

컨테이너는 `AutoUpdate=registry`로 설정되어 있어 `podman auto-update`로 이미지를 갱신할 수 있습니다.

### podman kube play

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

## 리버스 프록시

`nginx/adguard.conf`와 `caddy/adguard.caddyfile`은 `adguard.example.com`을 `127.0.0.1:80`으로 넘깁니다. TLS는 프록시에서 끝내고(edge 종료) AdGuard Home에는 HTTP로 넘깁니다. 호스트 이름과 인증서 경로를 실제 값으로 바꿔 씁니다. 웹 UI는 루트 경로(`/`)에서 엽니다.

프록시를 같은 호스트에서 실행하면 호스트 80/443이 겹칩니다. 그 서버에서는 AdGuard Home의 웹 UI 매핑을 `127.0.0.1:<포트>:80`처럼 바꾸고 443 매핑을 지운 뒤, 두 프록시 파일의 업스트림을 같은 포트로 맞춥니다. 설정 마법사(3000)는 프록시를 거치지 않으므로 `127.0.0.1:3000`이나 SSH 터널로 엽니다.

| 프록시 | 연결 방법 |
|---|---|
| Nginx | `nginx/adguard.conf`를 프록시의 `conf.d/`에 복사하고 `nginx -t` 후 다시 읽기 |
| Caddy | 프록시 Caddyfile에 `import /path/to/adguard.caddyfile`을 추가하고 `caddy validate --adapter caddyfile --config <Caddyfile>` 후 다시 읽기 |

두 파일은 같은 의미로 다음을 담습니다.

| 경로 | 허용 | 용도 |
|---|---|---|
| `/dns-query`, `/dns-query/<ClientID>` | 모두 | DNS-over-HTTPS |
| 그 밖의 경로 | 내부망(127/8, 10/8, 172.16/12, 192.168/16, ::1, fc00::/7) | 웹 UI. 외부에는 404 |

- TLS: 프록시에서 끝냅니다. Nginx는 80을 443으로 돌리고, Caddy는 인증서를 자동 발급합니다. AdGuard Home 암호화 설정의 **HTTPS로 자동 리다이렉트**(`tls.force_https`)는 끕니다. 켜면 프록시가 HTTP로 넘긴 요청을 AdGuard Home이 다시 HTTPS로 돌려보내 리다이렉트가 반복됩니다.
- 요청 본문: 사용자 규칙이나 허용/차단 목록을 한 번에 저장할 수 있게 두 파일 모두 10MB까지 허용합니다.
- DNS-over-HTTPS: 프록시가 HTTP로 넘기므로 `conf/AdGuardHome.yaml`에서 평문 DoH를 허용해야 합니다. 컨테이너를 멈추고 고친 뒤 다시 시작합니다.

  ```yaml
  tls:
    allow_unencrypted_doh: true
  ```

  DoH 클라이언트에는 `https://adguard.example.com/dns-query`를 지정합니다.
- 클라이언트 IP: AdGuard Home은 `dns.trusted_proxies`(기본 `127.0.0.0/8`, `::1`)에서 온 요청만 `X-Forwarded-For`, `X-Real-IP`를 믿습니다. 쿼리 로그에 클라이언트 대신 프록시나 컨테이너 게이트웨이 주소가 찍히면 그 주소를 `trusted_proxies`에 추가합니다. rootless Podman 포트 포워딩은 원본 IP를 보존하지 않을 수 있습니다.
- 다른 프록시나 로드밸런서 뒤에 있으면 내부망 판정이 앞단 주소로 이뤄집니다. Nginx는 `set_real_ip_from`, `real_ip_header`, Caddy는 전역 `servers { trusted_proxies ... }`와 `client_ip`로 실제 클라이언트 IP를 먼저 복원합니다.

## 주의 사항

- 설정 마법사는 인증 없이 열리므로 먼저 접속한 사람이 관리자 계정을 만들 수 있습니다. 실행 직후 마법사를 완료합니다. 그래서 3000번은 `127.0.0.1`에만 엽니다. 마법사를 마친 뒤에는 매핑을 지워도 됩니다.
- 포트가 모든 인터페이스에 열리므로 공인 IP가 있는 호스트에서는 방화벽으로 53, 80번을 내부망에만 허용합니다. 외부에 열린 DNS 서버는 DNS 증폭 공격에 악용됩니다. Docker가 공개한 포트는 ufw 규칙을 우회하므로 `DOCKER-USER` 체인이나 상위 방화벽에서 막습니다.
- 설정(`AdGuardHome.yaml`)은 `/opt/adguardhome/conf`, 쿼리 로그·통계·필터 데이터는 `/opt/adguardhome/work`에 저장됩니다. 호스트 쪽 데이터는 Compose `./data`, Quadlet `~/.local/share/adguard`, `podman kube play` PVC(`adguard-work`, `adguard-conf`)입니다. 지우면 관리자 계정과 설정도 함께 사라집니다.
- SELinux 호스트에서는 바인드 마운트에 `:Z`를 붙여 컨테이너 전용 라벨을 줍니다. 한 컨테이너만 쓰는 디렉터리이므로 공유 라벨(`:z`)은 쓰지 않습니다. SELinux가 꺼진 호스트에서는 무시됩니다. `pod.yaml`은 PVC(이름 있는 볼륨)를 쓰므로 라벨을 지정할 필요가 없습니다.
- 이미지는 root로 실행됩니다. rootless Podman에서 컨테이너 root는 호스트 사용자로 매핑되므로 데이터 파일은 호스트 사용자 소유가 됩니다. Quadlet은 마운트에 `U`를 붙여, 디렉터리를 다른 사용자(예: `sudo`)로 만들었거나 복사해 온 경우에도 시작할 때 소유권을 컨테이너 root에 맞춥니다. Docker는 `U`를 지원하지 않아 Compose에는 넣지 않았습니다. rootful Docker에서는 `data/` 안의 파일이 호스트 root 소유이므로 백업이나 삭제에 `sudo`가 필요합니다. rootless Podman에서 소유권이 어긋나면 `podman unshare chown -R 0:0 <디렉터리>`로 맞춥니다.
- `/opt/adguardhome` 전체를 마운트하면 이미지 안의 실행 파일까지 볼륨에 복사되어 이미지를 갱신해도 버전이 바뀌지 않습니다. 반드시 `work`, `conf`를 따로 마운트합니다.
- DHCP 서버 기능은 브리지 네트워크에서 동작하지 않습니다. 필요하면 호스트 네트워크(`network_mode: host`, Quadlet `Network=host`)로 바꾸고 포트 매핑을 제거합니다.
- rootless Podman은 네트워크 백엔드에 따라 쿼리 로그에 실제 클라이언트 IP 대신 내부 주소가 기록될 수 있습니다. 클라이언트별 통계가 중요하면 rootful 또는 호스트 네트워크로 실행합니다.
- DoH(`/dns-query`)는 프록시에서 외부에도 열려 있어 누구나 이 서버를 리졸버로 쓸 수 있습니다. 외부 사용자를 제한하려면 AdGuard Home의 **설정 → DNS 설정 → 접근 설정**에서 허용 클라이언트(ClientID 등)를 지정하거나, 프록시의 `/dns-query` 경로에도 내부망 제한을 겁니다.
- 이미지는 `latest`를 사용합니다. 재현성이 필요하면 검증한 버전으로 고정합니다.

## 참고 자료

- [AdGuard Home Docker 이미지](https://hub.docker.com/r/adguard/adguardhome)
- [AdGuard Home 위키 - Docker](https://github.com/AdguardTeam/AdGuardHome/wiki/Docker)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
