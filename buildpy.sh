#!/usr/bin/env bash

export PYTHON_VERSION="3.5.3"

rm -fr /tmp/buildp3 && \
    mkdir /tmp/buildp3 && \
    cd /tmp/buildp3 && \
    wget https://www.python.org/ftp/python/$PYTHON_VERSION/Python-${PYTHON_VERSION}.tgz && \
    tar -zxvf Python-${PYTHON_VERSION}.tgz && \
    cd Python-${PYTHON_VERSION} && \
    ./configure && \
    make && \
    make install && \
    rm -fr /tmp/buildp3
