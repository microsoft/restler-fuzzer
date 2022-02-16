FROM python:3.8-alpine

RUN apk add --no-cache build-base

COPY demo_server/  /app/demo_server
COPY requirements.txt logging.conf swagger.json /app/

WORKDIR /app

RUN pip install -r requirements.txt

EXPOSE 8878

ENV FLASK_RUN_HOST=0.0.0.0

CMD ["python", "demo_server/app.py"]
