FROM debian:10

MAINTAINER Mod Devices

ARG USER=modui
ARG GROUP=modui
ARG UID=1000
ARG GID=1000

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get -y update \
 && apt-get -y install --no-install-recommends python3-pip python3-dev python3-venv python3-setuptools git build-essential libasound2-dev libjack-jackd2-dev liblilv-dev libjpeg-dev zlib1g-dev \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /usr/share/man/?? /usr/share/man/??_*

RUN groupadd -g ${GID} ${GROUP} \
 && useradd -m ${USER} --uid=${UID} --gid=${GID}
USER ${UID}:${GID}

WORKDIR /home/modui

CMD /bin/bash ./docker/entrypoint.sh