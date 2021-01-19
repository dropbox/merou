# This lets you run Grouper or its tests inside of Docker.  Run it with:
#
# docker build -t grouper . && docker run -it -p 8888:8888 grouper
#
# You will be given a bash prompt and can press Ctrl-P to review several
# pre-written commands for running and testing the server.  If you want
# to edit files on your host and see the results immediately in the
# container, run it with:
#
# docker build -t foo . && docker run -it -p 8888:8888 --mount type=bind,source=$PWD,target=/app foo

# Tried building atop the simpler and smaller "python:2.7-slim" base,
# but its "MariaDB" replacement for MySQL dies with "Specified key was
# too long; max key length is 767 bytes" when our tests try creating
# their tables.
FROM ubuntu:20.04

RUN apt-get update

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get install -y libmysqlclient-dev mysql-client mysql-server
RUN apt-get install -y python3-dev python3-pip gcc
RUN apt-get install -y chromium-driver
RUN apt-get install -y procps unzip wget
RUN apt-get install -y libcurl4-openssl-dev libssl-dev

RUN wget --no-verbose -O /tmp/google-chrome-stable_current_amd64.deb https://dl.google.com/dl/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt-get install -y /tmp/google-chrome-stable_current_amd64.deb

ENV DB mysql
WORKDIR /app
COPY ci/setup.sh /app/ci/setup.sh
COPY requirements*.txt /app/

RUN /etc/init.d/mysql start && mysql -e "\
 CREATE USER travis@localhost; \
 GRANT ALL ON *.* TO travis@localhost; \
 "

RUN /etc/init.d/mysql start && \
 TRAVIS_PYTHON_VERSION=3.7 ci/setup.sh

COPY . /app
ENV PYTHONPATH /app
ENV GROUPER_SETTINGS /app/config/dev.yaml
ENV PATH="/app/chromedriver:${PATH}"

RUN bin/grouper-ctl -vv sync_db && \
 bin/grouper-ctl -vv user create user@example.com && \
 bin/grouper-ctl -vv group add_member --owner grouper-administrators user@example.com

RUN ( \
 echo 'MEROU_TEST_DATABASE='mysql://travis:@localhost/merou' py.test -x -v'; \
 echo 'py.test -x -v'; \
 echo 'tools/run-dev --user user@example.com --listen-host='; \
 ) > /root/.bash_history

EXPOSE 8888

ENV PYTHONDONTWRITEBYTECODE=PLEASE
ENV TRAVIS_PYTHON_VERSION 3.7
CMD ["/bin/bash", "-c", "/etc/init.d/mysql start && exec /bin/bash"]
