from fastapi import FastAPI, HTTPException, Depends

from hypercorn.config import Config
from hypercorn.asyncio import serve
import asyncio
import os, binascii
import uvicorn
import sys

from sqlmodel import create_engine, SQLModel, Session

from db import engine, get_session
from routers import blog, doc

app = FastAPI(title="Demo Blog Server",
    servers=[
            {"url": "https://localhost:8888", "description": "Staging environment"}]
)

app.include_router(blog.router)
app.include_router(doc.router)


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)



if __name__ == "__main__":

    app_port = os.getenv('DEMO_SERVER_PORT')
    if isinstance(app_port, int):
        app_port = int(app_port)
    else:
        app_port = 8888

    app_host = os.getenv('DEMO_SERVER_HOST')
    if app_host is None:
        app_host = "0.0.0.0"

    use_http2 = False
    for i in range(len(sys.argv)):
        if sys.argv[i] == '--use_http2':
            use_http2 = True

    if not use_http2:
        uvicorn.run("app:app", reload=True, host=app_host, port=app_port)
    else:
        config = Config()
        config.bind = [app_host + ":" + str(app_port)]
        loop = asyncio.get_event_loop()
        loop.run_until_complete(serve(app, config))


