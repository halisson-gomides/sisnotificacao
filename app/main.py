from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import asyncio
from .websocket_manager import manager, cleanup_task
from .models import NotificationCreate
import logging

# Configuração do logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Inicia task de limpeza em background
        tarefa_limpeza = asyncio.create_task(cleanup_task())
    except Exception as e:
        logger.error(f"Erro na inicialização: {e.__repr__()}")
        raise
    yield
    tarefa_limpeza.cancel()
    try:
        await tarefa_limpeza
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Sistema de Notificação", 
              lifespan=lifespan,
              docs_url=None)


# Middlewares para WebSocket (importante para Firefox)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, seja mais específico
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Headers específicos para WebSocket
@app.middleware("http")
async def add_websocket_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    return response

# Configuração de templates e arquivos estáticos
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# Rotas de páginas
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("monitor.html", {"request": request})


@app.get("/monitor", response_class=HTMLResponse)
async def monitor_page(request: Request):
    return templates.TemplateResponse("monitor.html", {"request": request})


@app.get("/display", response_class=HTMLResponse)
async def display_page(request: Request):
    return templates.TemplateResponse("display.html", {"request": request})


@app.delete("/api/notification/{notification_id}")
async def remove_notification(notification_id: str):
    """Remove uma notificação manualmente"""
    success = await manager.remove_notification(notification_id)
    return {"success": success, "notification_id": notification_id}


# WebSocket endpoints
@app.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    await manager.connect_monitor(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Monitores podem enviar mensagens de controle
            pass
    except WebSocketDisconnect:
        manager.disconnect_monitor(websocket)

@app.websocket("/ws/display")
async def websocket_display(websocket: WebSocket):
    await manager.connect_display(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Displays podem enviar confirmações
            pass
    except WebSocketDisconnect:
        manager.disconnect_display(websocket)

# API endpoints
@app.post("/api/send-notification")
async def send_notification(
    child_code: str = Form(...),
    priority: str = Form("normal"),
    message: str = Form(None)
):
    notification = await manager.create_notification(child_code, priority, message)
    return {"success": True, "notification_id": notification.id}

@app.post("/api/mark-viewed/{notification_id}")
async def mark_notification_viewed(notification_id: str):
    success = await manager.mark_as_viewed(notification_id)
    return {"success": success}

@app.get("/api/notifications")
async def get_notifications():
    return {"notifications": list(manager.notifications.values())}