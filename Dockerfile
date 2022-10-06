FROM python:3.7

RUN apt-get update && apt-get install -y cron
COPY messaging-crontab /etc/cron.d/messaging-crontab
RUN chmod 0644 /etc/cron.d/messaging-crontab && \
  crontab /etc/cron.d/messaging-crontab && \
  echo "starting crontab"

# use a script to run multiple (cron and gunicorn) in single container
COPY commands.sh /scripts/commands.sh
RUN ["chmod", "+x", "/scripts/commands.sh"]

WORKDIR /opt/app

ARG VERSION_STRING
ENV VERSION_STRING=$VERSION_STRING

COPY requirements.txt .
RUN pip install --requirement requirements.txt

COPY . .

ENV FLASK_APP=isacc_messaging.app:create_app() \
    PORT=8000

EXPOSE "${PORT}"

ENTRYPOINT ["/scripts/commands.sh", "${FLASK_APP}", "${PORT:-8000}"]
