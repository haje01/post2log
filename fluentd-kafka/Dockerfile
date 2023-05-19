FROM fluent/fluentd:v1.16

# Use root account to use apk
USER root

# below RUN includes plugin as examples elasticsearch is not required
# you may customize including plugins as you wish
RUN apk add --no-cache --update --virtual .build-deps \
        sudo build-base ruby-dev \
 && sudo gem install fluent-plugin-influxdb \
 && sudo gem install fluent-plugin-kafka \
 && sudo gem sources --clear-all \
 && apk del .build-deps \
 && rm -rf /tmp/* /var/tmp/* /usr/lib/ruby/gems/*/cache/*.gem

# RUN apk add --no-cache netcat-openbsd

# RUN apk --no-cache add ca-certificates wget
# RUN wget --quiet --output-document=/etc/apk/keys/sgerrand.rsa.pub https://alpine-pkgs.sgerrand.com/sgerrand.rsa.pub
# RUN wget https://github.com/sgerrand/alpine-pkg-kafkacat/releases/download/1.6.0-r0/kafkacat-1.6.0-r0.apk
# RUN apk add --no-cache kafkacat-1.6.0-r0.apk

USER fluent

