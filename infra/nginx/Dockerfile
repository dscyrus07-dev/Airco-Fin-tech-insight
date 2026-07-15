FROM nginx:1.27-alpine

RUN apk add --no-cache gettext curl

COPY nginx.ec2.conf.template /etc/nginx/nginx.ec2.conf.template
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 80 443

CMD ["/entrypoint.sh"]
