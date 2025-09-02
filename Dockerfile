# syntax=docker/dockerfile:1
# pull official base image
FROM python:3.11-slim
# set work directory
WORKDIR /usr/src/app
# set environment variables
ENV FLASK_APP=app/__init__.py
ENV FLASK_CONFIG=development
ENV FLASK_RUN_HOST 0.0.0.0

# install dependencies
RUN pip3 install --upgrade pip
COPY requirements requirements
RUN pip3 install -r requirements/requirements.txt
# copy project
COPY ./ /usr/src/app

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]