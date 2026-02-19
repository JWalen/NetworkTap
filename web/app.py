"""NetworkTap Web Dashboard - FastAPI Application."""

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from core.config import get_config
from core.auth import verify_credentials
from core.alert_parser import AlertWatcher
from core.stats_history import start_collector, stop_collector
from core.anomaly_detector import get_detector, start_anomaly_detection, stop_anomaly_detection
from api.routes_system import router as system_router
from api.routes_capture import router as capture_router
from api.routes_alerts import router as alerts_router
from api.routes_config import router as config_router
from api.routes_pcap import router as pcap_router
from api.routes_wifi import router as wifi_router
from api.routes_terminal import router as terminal_router, validate_command
from api.routes_users import router as users_router
from api.routes_stats import router as stats_router
from api.routes_rules import router as rules_router
from api.routes_backup import router as backup_router
from api.routes_reports import router as reports_router
from api.routes_syslog import router as syslog_router
from api.routes_zeek import router as zeek_router
from api.routes_ai import router as ai_router
from api.routes_update import router as update_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("networktap")

# WebSocket connections for live alerts
ws_clients: set[WebSocket] = set()

# Background alert watcher
alert_watcher: AlertWatcher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global alert_watcher
    config = get_config()
    logger.info("NetworkTap Web Dashboard starting on %s:%s", config.web_host, config.web_port)

    # Start background stats collector
    start_collector()

    # Start background alert watcher
    alert_watcher = AlertWatcher(config)
    watcher_task = asyncio.create_task(alert_watcher.watch(broadcast_alert))
    app.state.alert_watcher = alert_watcher

    # Start anomaly detection if enabled
    anomaly_task = None
    if config.anomaly_detection_enabled:
        async def anomaly_callback(anomaly: dict):
            await broadcast_alert({**anomaly, "alert_type": "anomaly"})
        anomaly_task = asyncio.create_task(start_anomaly_detection(anomaly_callback))
        logger.info("Anomaly detection started")

    yield

    # Shutdown
    stop_collector()
    stop_anomaly_detection()
    watcher_task.cancel()
    if anomaly_task:
        anomaly_task.cancel()
    for ws in list(ws_clients):
        try:
            await ws.close()
        except Exception:
            pass
    logger.info("NetworkTap Web Dashboard stopped")


app = FastAPI(
    title="NetworkTap",
    description="Network Tap Appliance Dashboard",
    version="1.0.13",
    lifespan=lifespan,
)

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include API routers
app.include_router(system_router, prefix="/api/system", tags=["System"])
app.include_router(capture_router, prefix="/api/capture", tags=["Capture"])
app.include_router(alerts_router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(config_router, prefix="/api/config", tags=["Config"])
app.include_router(pcap_router, prefix="/api/pcaps", tags=["PCAPs"])
app.include_router(wifi_router, prefix="/api/wifi", tags=["WiFi"])
app.include_router(terminal_router, prefix="/api/terminal", tags=["Terminal"])
app.include_router(users_router, prefix="/api/users", tags=["Users"])
app.include_router(stats_router, prefix="/api/stats", tags=["Stats"])
app.include_router(rules_router, prefix="/api/rules", tags=["Rules"])
app.include_router(backup_router, prefix="/api/backup", tags=["Backup"])
app.include_router(reports_router, prefix="/api/reports", tags=["Reports"])
app.include_router(syslog_router, prefix="/api/syslog", tags=["Syslog"])
app.include_router(zeek_router, prefix="/api/zeek", tags=["Zeek"])
app.include_router(ai_router, prefix="/api/ai", tags=["AI"])
app.include_router(update_router, prefix="/api/update", tags=["Update"])


async def broadcast_alert(alert: dict):
    """Broadcast an alert to all connected WebSocket clients."""
    disconnected = set()
    for ws in ws_clients:
        try:
            await ws.send_json(alert)
        except Exception:
            disconnected.add(ws)
    ws_clients.difference_update(disconnected)


@app.websocket("/ws/alerts")
async def websocket_alerts(ws: WebSocket):
    """WebSocket endpoint for real-time alert streaming."""
    await ws.accept()
    ws_clients.add(ws)
    logger.info("WebSocket client connected (%d total)", len(ws_clients))
    try:
        while True:
            # Keep connection alive, wait for client messages (e.g., pings)
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(ws_clients))


@app.websocket("/ws/terminal")
async def websocket_terminal(ws: WebSocket):
    """WebSocket endpoint for terminal command execution."""
    await ws.accept()
    authenticated = False

    try:
        # First message must be auth
        auth_data = await asyncio.wait_for(ws.receive_json(), timeout=10)
        config = get_config()

        user_ok = secrets.compare_digest(
            (auth_data.get("user", "") or "").encode(),
            config.web_user.encode(),
        )
        pass_ok = secrets.compare_digest(
            (auth_data.get("pass", "") or "").encode(),
            config.web_pass.encode(),
        )

        if not (user_ok and pass_ok):
            await ws.send_json({"type": "auth", "data": "fail"})
            await ws.close()
            return

        authenticated = True
        await ws.send_json({"type": "auth", "data": "ok"})
        logger.info("Terminal WebSocket authenticated")

        # Command loop
        while True:
            msg = await ws.receive_json()
            cmd = msg.get("cmd", "").strip()
            if not cmd:
                continue

            # Validate against whitelist
            error = validate_command(cmd)
            if error:
                await ws.send_json({"type": "stderr", "data": f"Blocked: {error}\n"})
                await ws.send_json({"type": "exit", "code": -1})
                continue

            # Execute command with 30s timeout
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                async def stream_pipe(pipe, msg_type):
                    while True:
                        line = await pipe.readline()
                        if not line:
                            break
                        await ws.send_json({
                            "type": msg_type,
                            "data": line.decode("utf-8", errors="replace"),
                        })

                try:
                    await asyncio.wait_for(
                        asyncio.gather(
                            stream_pipe(proc.stdout, "stdout"),
                            stream_pipe(proc.stderr, "stderr"),
                        ),
                        timeout=30,
                    )
                    code = await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()
                    await ws.send_json({"type": "stderr", "data": "Command timed out (30s limit)\n"})
                    code = -1

                await ws.send_json({"type": "exit", "code": code})

            except Exception as e:
                await ws.send_json({"type": "stderr", "data": f"Error: {e}\n"})
                await ws.send_json({"type": "exit", "code": -1})

    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        try:
            await ws.close()
        except Exception:
            pass
    except Exception as e:
        logger.error("Terminal WebSocket error: %s", e)
    finally:
        logger.info("Terminal WebSocket disconnected")


@app.get("/", include_in_schema=False)
async def index():
    """Serve the SPA shell."""
    return FileResponse(Path(__file__).parent / "templates" / "index.html")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "networktap"}
