FROM me/gapi-base:latest

ARG gsfId
ENV gsfId=${gsfId}
ARG authSubToken
ENV authSubToken=${authSubToken}

RUN mkdir persist && mkdir persist/apks

COPY main.py .

CMD python main.py