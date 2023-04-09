FROM python:alpine as builder

RUN pip install --ignore-installed --target=/modules jsonpickle

FROM me/python-gpapi:latest

ARG gsfId
ENV gsfId=${gsfId}
ARG authSubToken
ENV authSubToken=${authSubToken}

RUN mkdir persist && mkdir persist/apks

COPY --from=builder /modules /
COPY main.py .

ENTRYPOINT python3 main.py