# post2log

외부 서버에서 HTTP Postback 호출 (POST 메소드) 을 받으면, 그 내용을 로그로 기록한 후 [Fluentd](https://www.fluentd.org/) 등을 통해 외부의 다양한 대상으로 포워딩할 수 있다. post2log 는 쿠버네티스 환경에서 설치 및 이용한다.

post2log 는 자체 서버와 Fluentd 가 같은 노드에 설치되어 함께 동작한다. 내장된 Fluentd 컨테이너 이미지는 다음과 같은 플러그인이 미리 설치되어 있다.
- `fluentd-plugin-kafka`
- `fluentd-plugin-influxdb`

## 설정

`helm/values.yaml` 에서 변수와 그 기본값을 확인할 수 있다. 아래는 그 내용이다.

```yaml
# Helm 차트 기본값
server:
  image: 
    registry: ""
    repository: library/post2log-server
    tag: 0.2.23
    digest: ""
fluentd:
  image: 
    registry: ""
    repository: library/post2log-fluentd
    tag: 0.2.23
    digest: ""
  # Fluentd 용 스토리지 크기
  storage: 4Gi
  # 복제할 필드 리스트
  duplicateFields: {}
  # Fluentd 최종 출력 설정
  extraCfg: |
    <match {{ .Release.Name }}>
      @type stdout
    </match>"
# 포스트백 서버 포트. 기본값 80
port: 80 
# 노드 당 하나의 post2log 만 존재할지 여부
nodeExclusive: true
# 노드포트 이용시 포트. 공백이면 사용 않음
nodePort: ""
# 배포 대상 노드 셀렉터
nodeSelector: {}
logQueryParam: true
# 값이 Null 인 필드 제외 여부
skipNullFields: true
ingress:
  # 자체 Ingress 사용 여부
  enabled: false
  hostname: ""
  annotations: {}
# 포스트백 서버 (FastAPI) 의 워커 수
workers: 1
# 포스트백 서버의 레플리카(파드) 수
replicas: 1
# 로그 저장 스토리지 크기
storage: 4Gi
# 로그 파일 로테이션 기준 바이트수
rotBytes: "10485760"
# 로그 파일 로테이션 백업 수
rotBackups: 5
uvicorn:
  # Uvicorn 로그 레벨
  logLevel: debug
```

> `duplicateFields` 블럭에는 복제할 필드의 이름과 새 필드의 이름 쌍이 나열되는데, Fluentd 의 한계상 대상 필드가 있는 경우 새 필드로 복제되고, 없는 경우 `NA` 로 채워진 새 필드가 만들어진다.

## 배포 

배포를 위해선는 용도에 맞게 위 변수 파일을 수정하여 저장하여 그것을 이용한다. `configs/` 폴더 아래에 다양한 설정 파일의 예제가 있다.

post2log 는 버전 관리를 단순히하기 위해 Helm 차트 버전과 앱 버전(=컨테이너 이미지 버전) 을 하나로 통일한다. Dockerfile, 소스코드 및 매니페스트 파일을 수정 할 때마다 차트와 앱버전을 동시에 올려주는 방식이다. (버전은 'helm/Chart.yaml` 참조)

> 버전 업을 할 때는 `helm/` 폴더 아래에서, 다음처럼 `chartrepo/` 도 함께 갱신해주자.
> ```
> helm package .
> mv post2log-0.2.23.tgz chartrepo/
> cd chartrepo && 
> helm repo index .
> git add post2log-0.2.23.tgz
> ```

먼저 이미지를 빌드해야 하는데, Skaffold 를 이용해 아래와 같이 진행한다.

```bash
skaffold build --tag=0.2.23 --push --default-repo=docker.io/haje01
```

> 위 경우 Docker Login 이 필요하다. 커스텀 이미지를 이용하려 하는 경우 자신의 리포지토리로 교체하자.

### 로컬 배포

`configs/local.yaml` 은 로컬용 변수 파일인데, 이것을 이용해 아래와 같이 Helm 으로 설치할 수 있다.

```bash
helm install -f configs/local.yaml test helm/
```

포스트백을 받을 엔드포인트는 `/postback/설치명` 형식으로 구성된다. 위 설치의 경우 엔드포인트는 `/postback/test` 이다.


Helm 으로 설치시는 기본 레지스트리인 `docker.io` 를 이용한다.

`skaffold.yaml` 의 `local` 프로파일에는 `configs/local.yaml` 을 이용하도록 지정되어 있기에 다음과 같이 Skaffold 프로파일을 지정해 설치할 수도 있다. 단, 이경우 `P2L_RELEASE` 환경 변수에 배포명을 지정해야 한다.

> `skaffold.yaml` 의 배포명을 이용하지 않는 것은, 설정의 종류와 배포명이 묶이기 때문이다. 

Skaffold 로 설치시는 쿠버네티스 환경에 로컬 컨테이너 이미지 레지스트리가 있는 경우 그것을 이용할 수 있다.

```bash
P2L_RELEASE=local skaffold run -p local
```

아니라면 다음과 같이 기본 레포지토리를 명시해준다. 

```bash
P2L_RELEASE=test skaffold run -p local --default-repo=docker.io/haje01
```

테스트를 위해서 로컬 클러스터에서는 포트포워딩을 해주고,

```bash
kubectl port-forward svc/post2log 8080:80
```

`curl` 을 통해 POST 호출을 수행한 뒤,

```bash
curl -X POST "localhost:8080/postback?p1=v1&p2=v2"
```

> 이때 엔드포인트가 맞지 않으면 `{"detail":"Not Found"}` 가 출력되고, 성공하면 `{"status":"success"}` 가 출력된다.

`stdout` 출력의 경우 `kubectl logs` 명령으로 Fluentd 파드의 로그를 보면 결과를 확인할 수 있다. 예를들어 아래와 같은 식으로 남는다.

```
2023-04-28 09:57:43.291989606 +0000 post2log: {"p1":"v1","p2":"v2","_path":"/postback","_timestamp":1682675862705,"_dateTimeGMT":"2023-04-28T09:57:42Z","_nodeName":"minikube","_workerPodHash":"7bcd9d6cdf-7jmsd","_workerProcId":"1"}
```

언더바 `_` 가 붙은 필드는 쿼리 인자값이 아닌 post2log 에서 생성한 필드로 다음과 같은 것들이 있다:
- `_path` - 호출의 엔드포인드 경로
- `_timestamp` - 호출의 타임스탬프
- `_dateTimeGMT` - 호출의 UTC 기준 일시


### 외부 인그레스 이용

외부 서버에 `K3s` 같은 쿠버네티스 배포본으로 클러스터를 설치하였다면, 배포판에 맞는 Ingress 의 Annotation 을 설정해 이용할 수 있다. 다음은 `configs/ingress.yaml` 에서 가져온 것으로, K3s 에서 기본 인그레스 컨트롤러인 Traefik 을 이용하는 설정이다.

```yaml
ingress:
  enabled: true
  hostname: k3s.remote
  annotations: 
  - kubernetes.io/ingress.class: traefik
```

### Kafka 로 출력 

다음은 `configs/kafka.yaml` 파일의 내용으로, 수집된 로그를 카프카로 보내는 예이다.

```yaml
ingress:
  enabled: fase
fluentd: 
  extraCfg: |
    <match {{ .Release.Name }}> 
      @type kafka2
      brokers <카프카 IP>:<카프카 Port>
      use_event_time true
      default_topic {{ .Release.Name }}
      
      <format>
        @type json
      </format>

      <buffer>
        @type memory
        flush_mode interval
        flush_interval 10s
      </buffer>

      # 디버깅용
      # @log_level trace
      # get_kafka_client_log true
    </match>"

    <system>
      log_level info
    </system>
```

위와 같이 하면, 엔드포인트 `/postback/test` 호출의 내용을 Kafka 의 `test` 토픽으로 저장하게 된다. 

> Fluentd 카프카 플러그인은 Kafka 에서 메시지를 보낼 파티션 리더의 도메인 명을 얻어와 접속을 시도하기에, post2log 가 설치된 서버에서 도메인 이름으로 각 브로커에 접속할 수 없다면 다음과 같은 방식을 검토해야 한다:
> - Fluentd 장비의 /etc/hosts 에 도메인 등록하기
> - 쿠버네티스 환경의 경우 같은 클러스터내에 배포하기 

## InfluxDB 로 출력 

다음은 `configs/kafka.yaml` 파일의 내용으로, 수집된 로그를 InfluxDB 로 보내는 예이다.

```yaml
ingress:
  enabled: fase
skipNullFields: true
fluentd: 
  extraCfg: |
    <match {{ .Release.Name }}> 
      @type influxdb
      host <카프카 IP>:<카프카 Port>
      port 8086
      dbname post2log
      user admin
      password admindjemals
      time_precision ns
      use_ssl false
      <buffer>
        @type memory
        chunk_limit_size 1m
        flush_mode interval
        flush_interval 10
      </buffer>
    </match>

    <system>
      log_level trace
    </system>
```

위와 같이 하면, 엔드포인트 호출의 내용을 InfluxDB 의 `post2log` 데이터베이스 아래 `test` 메저먼트 (Measurement) 로 저장하게 된다. 

> InfluxDB 에 `post2log` 데이터베이스는 미리 만들어 두어야 한다.

InfluxDB 는 null 값을 직접 지원하지 않기에, 기본적으로 null 값이 있는 레코드는 생략되게 된다. 예제에서는 이를 방지하기 위해서는 `skipNullFields` 을 `true` 로 설정하였다.

## 최적화와 배포

### 적절한 워커 수와 레플리카 지정

`workers` 를 늘리는 경우 uvicorn 서버의 워커를 늘리는 것인데, 이 경우 파드의 CPU 리소스 제한을 적절히 설정해 주어야 할 것이다. `replicas` 를 늘리면 post2log 서버의 파드 수가 늘어나 분산 처리의 효과를 기대할 수 있으나 적절히 노드를 추가해 주어야 할 것이다. 

기본적으로 HTTP 요청을 FastAPI 를 통해 비동기로 받은 뒤 파일에 저장하는 단순한 일이기에, 클러스터 노드를 추가하거나 `workers` 나 `replicas` 를 늘려주는 것으로 성능이 바로 향상되지 않을 수 있다. Fluentd 설정에 따른 다운스트림 작업의 경중에도 영향을 받을 것으로 생각되기에, 필요한 설정 후 최적화를 위한 다양한 실험이 필요할 것이다.

### 배포

성능을 위해 post2log 의 서버와 Fluentd 는 노드 당 하나씩만 존재해야 한다. 이를 위해 `podAntiAffinity` 가 설정되어 이미 post2log 파드가 있는 노드에는 배포되지 않는 것에 유의하자. 예를 들어 `replicas` 의 값을 3 으로 했다면, 실제 쿠버네티스 클러스터의 워커 노드도 세 대가 필요하다.

### 대상 노드 선택

클러스터에 다양한 노드가 있는 경우, post2log 레플리카를 특정 노드에만 배포하려면 `nodeSelector` 을 이용한다. 예를 들어 다음처럼 특정 노드에 `noderole=ingest` 라벨을 붙여주고, 

```bash
kubectl label nodes svr-01 svr-02 noderole=ingest
```
post2log 설치시 `nodeSelector` 에 같은 값을 지정하면 `ingest` 라벨이 있는 노드에만 배포된다.
