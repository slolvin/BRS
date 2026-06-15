# syntax=docker/dockerfile:1
# pull official base image
FROM python:3.12-slim
# set work directory
WORKDIR /usr/src/app
# set environment variables
ENV FLASK_APP=app.py
ENV FLASK_CONFIG=development
ENV FLASK_RUN_HOST=0.0.0.0

# install dependencies
COPY requirements/ ./requirements/
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements/requirements.txt
# copy project
COPY ./ /usr/src/app

CMD [ "python3", "-m" , "flask", "run"]