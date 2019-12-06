FROM python:2

ENV PYTHONUNBUFFERED 1

RUN mkdir /code
RUN mkdir /cert

WORKDIR /code

COPY requirements.txt /code/

# EXPOSE 8000

RUN pip install -r requirements.txt

COPY . /code/

COPY ../x509/pwpearson.com/ /cert/

# CMD [ "python", "manage.py", "runsslserver", "0.0.0.0:8000" ]

