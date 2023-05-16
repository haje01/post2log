# 첫 번째 빌드 스테이지: 플러그인 설치
FROM fluent/fluentd:v1.16 as builder

# 필요한 라이브러리와 헤더 설치 
USER root
RUN apk --no-cache --update add build-base ruby-dev 
RUN fluent-gem install fluent-plugin-kafka

# 두 번째 빌드 스테이지: 최종 이미지 생성
FROM fluent/fluentd:v1.16

# 첫 번째 스테이지에서 설치한 플러그인을 복사
COPY --from=builder /fluentd/plugins/* /fluentd/plugins/