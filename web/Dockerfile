FROM alpine:latest
RUN apk add python3 py3-flask py3-lxml py3-gunicorn

ENV PYTHONUNBUFFERED True

ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
