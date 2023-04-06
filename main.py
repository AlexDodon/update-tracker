#!python
import signal
import sys
import jsonpickle
import json
import os
import logging as l
from typing import List, Dict
from pprint import pformat
from datetime import datetime
import concurrent.futures as futures
import time
from gpapi.googleplay import GooglePlayAPI

class Base:
    def __repr__(self):
        return pformat(vars(self), indent=2)


class DetailsExcerpt(Base):
    def __init__(self, details: dict[str, any], timestamp: float):
        self.name = details['docid']
        details = details['details']
        appDetails = details['appDetails']
        self.version = appDetails['versionString']
        self.versionCode = appDetails['versionCode']
        uploadDate = appDetails['uploadDate']
        self.uploadDate = datetime.strptime(uploadDate, '%b %d, %Y').timestamp()
        self.seen = timestamp

def init():
    signal.signal(signal.SIGINT, signal.default_int_handler)

    email =             os.environ.get('mail')
    password =          os.environ.get('passwd')
    authSubToken =      os.environ.get('authSubToken')
    gsfId =             os.environ.get('gsfId')
    gsfId =             gsfId if gsfId == None else int(gsfId)
    logFile =           os.environ.get('logFile', 'updateTracking.log')
    handlesFile =       os.environ.get('handlesFile', 'handles.json')
    lastUpdatesFile =   os.environ.get('lastUpdatesFile', 'lastUpdates.json')

    l.basicConfig(filename=f'persist/{logFile}', level=l.INFO, format='[%(asctime)s][%(threadName)12s][%(levelname)7s]: %(message)s')

    executor = futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix='Downloader')

    api = GooglePlayAPI(locale="en_US", timezone="UTC", device_codename="hero2lte")

    try:
       api.login(email=email, password=password, authSubToken=authSubToken, gsfId=gsfId)
    except Exception as e:
       l.error('Could not login')
       raise e

    if email != None and password != None:
        l.info(f'Logged in with email and password. The new gsfId is "{api.gsfId}". The new authSubToken is "{api.authSubToken}"')

    try:
        f = open(f'persist/{handlesFile}', 'r')
        handles = json.load(f)
    except Exception as e:
        l.error(f'Could not read the handles file: {handlesFile}')
        raise e
    finally:
        f.close()

    try:
        f = os.open(f'persist/{lastUpdatesFile}', os.O_RDWR | os.O_CREAT)
        f = os.fdopen(f, 'r+')
        f.seek(0)
    except Exception as e:
        l.error(f'Could not open the lastUpdates file: {lastUpdatesFile}')
        f.close()
        raise e
    
    try:
        text = f.read()
        lastUpdates: Dict[str, DetailsExcerpt] = jsonpickle.decode(text)
    except json.JSONDecodeError as e:
        l.warning(f'Could not decode a json object from {lastUpdatesFile}. Assuming this is a fresh run {e}')
        lastUpdates: Dict[str, DetailsExcerpt] = dict()
    except Exception as e:
        l.error(f'Could not read and decode the {lastUpdatesFile} file')
        raise e

    return executor, api, handles, lastUpdates, f

def download(api: GooglePlayAPI, excerpt: DetailsExcerpt):
    sleepTime = 29
    l.info(f'### Starting the download for {excerpt.name}')
    app = api.download(packageName=excerpt.name, versionCode=excerpt.versionCode, expansion_files=True)
    
    l.info('Saving apk to disk')
    date = datetime.fromtimestamp(excerpt.seen).strftime('%Y-%m-%d-%H:%M:%S.%f')
    with open(f'persist/apks/{app["docId"]}-{date}-{excerpt.versionCode}.apk', 'wb') as first:
        for chunk in app.get('file').get('data'):
            first.write(chunk)

    l.info('Saving additional data to disk.')
    for obb in app['additionalData']:
        l.info(f'Saving {obb["type"]}')
        with open(f'persist/apks/{app["docId"]}-{date}-{obb["type"]}-{obb["versionCode"]}.obb', 'wb') as second:
            for chunk in obb.get('file').get('data'):
                second.write(chunk)
    
    l.info(f'Sleeping {sleepTime} seconds')
    time.sleep(sleepTime)


def main():
    sleepSeconds = 15 * 60
    executor, api, handles, lastUpdates, lastUpdatesFile = init()

    l.info('### Init done')
    try:
        while True:
            l.info('### Bulk checking details')
            checkTime = datetime.now().timestamp()
            appDetails = api.bulkDetails(handles)
            l.info(f'Received a response for {len(appDetails)} handles. Parsing them')

            excerpts: List[DetailsExcerpt] = []

            for (handle, detail) in zip(handles, appDetails):
                try:
                    excerpts.append(DetailsExcerpt(detail, checkTime))
                except Exception as e:
                    l.error(f'Could not get the details excerpt for {handle}')

            l.info(f'Parsed {len(excerpts)} excerpts')

            shouldWriteLastUpdates = False

            for excerpt in excerpts:
                entry = lastUpdates.get(excerpt.name, None)

                if entry == None or excerpt.uploadDate > entry.uploadDate:
                    lastUpdates[excerpt.name] = excerpt
                    shouldWriteLastUpdates = True
                    l.info(f'For handle {excerpt.name} found new upload from {datetime.fromtimestamp(excerpt.uploadDate).strftime("%Y-%m-%d")}. Queueing download')
                    executor.submit(download, api, excerpt)

            if shouldWriteLastUpdates:
                l.info('Updated the last updates dict. Writing it to disk')
                try:
                    lastUpdatesFile.seek(0)
                    lastUpdatesFile.write(jsonpickle.encode(lastUpdates, indent=2))
                    lastUpdatesFile.truncate()
                except Exception as e:
                    l.error('Could not write the last Updates file. Aborting')
                    raise e

            l.info(f'Sleeping for {sleepSeconds / 60} minutes')

            time.sleep(sleepSeconds)
    except KeyboardInterrupt:
        l.info('### Received interrupt. Shutting down')
    finally:
        lastUpdatesFile.close()
        executor.shutdown()
        l.info('Shutdown\n\n\n')

if __name__ == '__main__':
    main()
