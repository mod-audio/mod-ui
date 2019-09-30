FROM debian:stable

RUN apt-get update

RUN apt-get install -y \
    virtualenv \
    python3-pip \
    python3-dev \
    git \
    build-essential \
    libasound2-dev \
    libjack-jackd2-dev \
    liblilv-dev \
    libjpeg-dev \
    zlib1g-dev \
    python2
    

ENV LV2_PATH="/lv2"
ENV MOD_DEV_HOST=1
ENV MOD_DEV_ENVIRONMENT=0

RUN mkdir /mod-lv2-data
RUN mkdir /lv2
WORKDIR /mod-lv2-data
RUN git clone https://github.com/moddevices/mod-lv2-data.git
RUN mv mod-lv2-data/plugins-fixed/* /lv2
RUN rm -rf mod-lv2-data

RUN mkdir /mod-ui

COPY ./ /mod-ui/

WORKDIR /mod-ui

RUN virtualenv modui-env
RUN chmod a+x activate-env
RUN ./activate-env

RUN pip3 install -r requirements.txt
RUN make -C utils

EXPOSE 8888

VOLUME ["/lv2", "/mod-ui"]

CMD python3 ./server.py
