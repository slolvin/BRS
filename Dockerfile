# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /usr/src/app
ENV FLASK_APP=app.py
ENV FLASK_CONFIG=development
ENV FLASK_RUN_HOST=0.0.0.0

COPY requirements/ ./requirements/
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements/requirements.txt
COPY ./ .

CMD [ "python3", "-m" , "flask", "run"]