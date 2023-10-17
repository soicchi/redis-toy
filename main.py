from fastapi import FastAPI, Depends
from redis import asyncio as aioredis
from starlette.responses import HTMLResponse
from starlette.websockets import WebSocket
from starlette.staticfiles import StaticFiles
import asyncio
import uvloop
import uvicorn
import datetime
import os
import logging

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

redis = aioredis.from_url(f"redis://{os.getenv('REDIS_HOST')}", encoding="utf-8", decode_responses=True)

class Constants:
    APP_HOST = os.getenv("APP_HOST")
    APP_PORT = int(os.getenv("APP_PORT"))
    STREAM_MAX_LEN = int(os.getenv("STREAM_MAX_LEN"))

async def read_message(websocket: WebSocket, join_info: dict):
    connected = True
    is_first = True
    stream_id = "$"

    while connected:
        try:
            count = 1 if is_first else 100
            results = await redis.xread(
                streams={join_info["room"]: stream_id},
                count=count,
                block=100000,
            )

            for room, events in results:
                if join_info["room"] != room:
                    continue
                
                for event_id, event in events:
                    now = datetime.datetime.now()

                    await websocket.send_text(f"{now.strftime('%H:%M:%S')} {event[b'message']}")

                    stream_id = event_id

                if is_first:
                    is_first = False
        except Exception as e:
            logging(e)
            await redis.aclose()
            connected = False


async def write_message(websocket: WebSocket, join_info: dict):
    await notify(join_info, "joined")

    connected = True
    while connected:
        try:
            data = await websocket.receive_text()
            await redis.xadd(
                join_info["room"],
                {
                    "username": join_info["username"],
                    "message": data
                },
                id=b"*",
                maxlen=Constants.STREAM_MAX_LEN,
            )
        except Exception as e:
            logging(e)
            await notify(join_info, "left")
            await redis.aclose()
            connected = False


async def notify(join_info: dict, action: str):
    await redis.xadd(
        join_info["room"],
        {"message": f"{join_info['username']} has {action}"},
        id=b"*",
        maxlen=Constants.STREAM_MAX_LEN,
    )


async def get_join_info(username: str = None, room: str = None):
    return {"username": username, "room": room}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, join_info: dict = Depends(get_join_info)):
    await websocket.accept()
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    await asyncio.gather(write_message(websocket, join_info), read_message(websocket, join_info))


if __name__ == "__main__":
    uvicorn.run(app, host=Constants.APP_HOST, port=Constants.APP_PORT)
