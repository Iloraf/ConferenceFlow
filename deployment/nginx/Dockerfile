FROM nginx:1.27

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl socat openssl libnginx-mod-stream \
    && rm -rf /var/lib/apt/lists/*

RUN curl https://get.acme.sh | sh

# replace existing files by our own configs
RUN rm /etc/nginx/nginx.conf && rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/
COPY ./conf.d/app.conf /etc/nginx/conf.d/

ARG APP
ENV APP="${APP}" DOLLAR='$'

# Créer les répertoires nécessaires
RUN mkdir -p /var/www/certbot/.well-known/acme-challenge
RUN mkdir -p /etc/letsencrypt/live

COPY ./bin/entrypoint.sh /entrypoint.sh
COPY ./bin/renew /etc/periodic/monthly/renew
RUN chmod +x /entrypoint.sh /etc/periodic/monthly/renew

ENTRYPOINT ["../entrypoint.sh"]

#FROM nginx:alpine-slim

#RUN apk update && apk add --no-cache curl socat openssl

# Installer acme.sh
#RUN curl https://get.acme.sh | sh -s email=noreply@example.com

# replace existing files by our own configs
#RUN rm /etc/nginx/nginx.conf && rm /etc/nginx/conf.d/default.conf
#COPY nginx.conf /etc/nginx/
#COPY ./conf.d/app.conf /etc/nginx/conf.d/

#ARG APP
#ENV APP="${APP}" DOLLAR='$'

# Créer les répertoires nécessaires
#RUN mkdir -p /var/www/certbot/.well-known/acme-challenge
#RUN mkdir -p /etc/letsencrypt/live

#COPY ./bin/entrypoint.sh /entrypoint.sh
#COPY ./bin/renew /etc/periodic/weekly/renew
#RUN chmod +x /entrypoint.sh /etc/periodic/weekly/renew

#ENTRYPOINT ["../entrypoint.sh"]
#ENTRYPOINT ["/bin/sh", "-c", "/entrypoint.sh && tail -f /dev/null"]
