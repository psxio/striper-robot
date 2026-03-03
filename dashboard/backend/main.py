"""FastAPI entry point for the striping robot dashboard."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import jobs, paths, robot
from .services import job_store
from .services.ros_bridge import ros_bridge

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await job_store.init_db()
    await ros_bridge.start()
    yield
    # Shutdown
    await ros_bridge.stop()


app = FastAPI(
    title="Striper Robot Dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow everything during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(jobs.router)
app.include_router(robot.router)
app.include_router(paths.router)


# WebSocket for live robot status
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    await ros_bridge.register_ws(ws)
    try:
        while True:
            # Keep connection alive; client may send pings or commands
            data = await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ros_bridge.unregister_ws(ws)


# Serve frontend static files (must be last so it doesn't shadow API routes)
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
