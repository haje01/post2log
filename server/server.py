import os
import json
from typing import Dict
from urllib.parse import parse_qs
from datetime import datetime, timezone
import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request

LOG_FORMAT = '%(message)s'
LOG_ROT_BYTES = int(os.environ.get('LOG_ROT_BYTES', 1024 * 1024))
LOG_ROT_BACKUPS = int(os.environ.get('LOG_ROT_BACKUPS', 5))
LOG_QUERYPARAM = os.environ.get('LOG_QUERYPARAM', 'true')
POD_NAME = os.environ.get('POD_NAME', 'NA')
ENDPOINT = os.environ.get('ENDPOINT', '/postback')

print(f"ENDPOINT: {ENDPOINT}")

app = FastAPI()
worker_id = os.getpid()
log_queryparam = LOG_QUERYPARAM.lower() == 'true'


def create_logger(worker_id: int):
    logger = logging.getLogger(f"worker_{worker_id}")
    logger.setLevel(logging.INFO)

    log_filename = f"/data/{POD_NAME}_{worker_id}.txt"
    handler = RotatingFileHandler(log_filename, maxBytes=LOG_ROT_BYTES, backupCount=LOG_ROT_BACKUPS)
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)    
    logger.addHandler(handler)

    return logger

logger = create_logger(worker_id)


@app.get('/')
@app.get('/healthz')
def health():
    return 'ok'


@app.post(ENDPOINT)
async def postback(request: Request):
    if log_queryparam:
        params = dict(request.query_params)

    raw_data = await request.body()
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON data - {}".format(raw_data)}
    now = datetime.now(timezone.utc)
    post_ts = int(now.timestamp() * 1000)
    post_gmtdt = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    content = params if log_queryparam else {}
    content.update(data)
    content.update({
        '_path': ENDPOINT,
        '_postTimestamp': post_ts, 
        '_postDatetimeGMT': post_gmtdt,
        }
    )
    logger.info(json.dumps(content))
    return {"status": "success"}
