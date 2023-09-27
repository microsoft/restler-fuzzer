from fastapi import FastAPI, HTTPException, Depends

import uvicorn
import os, binascii

from sqlmodel import create_engine, SQLModel, Session

from db import engine, get_session
from routers import blog, doc

app = FastAPI(title="Demo Blog Server",
    servers=[
            {"url": "http://localhost:8888", "description": "Staging environment"}]
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

    uvicorn.run("app:app", reload=True, host=app_host, port=app_port)

