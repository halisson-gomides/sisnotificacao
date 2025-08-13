from fastapi import WebSocket
from typing import List, Dict, Optional
import json
import asyncio
from datetime import datetime, timedelta
from .models import Priority, Notification, NotificationStatus
import uuid
import logging

# Configurar logging para debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Armazena conexões por tipo (monitor/display)
        self.monitors: List[WebSocket] = []
        self.displays: List[WebSocket] = []
        # Armazena notificações ativas
        self.notifications: Dict[str, Notification] = {}
        # NÃO usar timers automáticos no backend - deixar frontend controlar
        

    async def connect_monitor(self, websocket: WebSocket):
        await websocket.accept()
        self.monitors.append(websocket)
        logger.info(f"Monitor conectado. Total: {len(self.monitors)}")
        
        # Enviar estado atual para o novo monitor
        await self.send_current_state(websocket)
        
        # Notificar todos os monitores sobre nova conexão
        await self.broadcast_monitor_count()

        
    async def connect_display(self, websocket: WebSocket):
        await websocket.accept()
        self.displays.append(websocket)
        logger.info(f"Display conectado. Total: {len(self.displays)}")
        # Envia notificações pendentes
        await self.send_pending_notifications(websocket)

        
    def disconnect_monitor(self, websocket: WebSocket):
        if websocket in self.monitors:
            self.monitors.remove(websocket)
            logger.info(f"Monitor desconectado. Total: {len(self.monitors)}")
            # Atualizar contagem para monitores restantes
            asyncio.create_task(self.broadcast_monitor_count())

            
    def disconnect_display(self, websocket: WebSocket):
        if websocket in self.displays:
            self.displays.remove(websocket)
            logger.info(f"Display desconectado. Total: {len(self.displays)}")

    
    async def send_current_state(self, websocket: WebSocket):
        """Envia o estado atual das notificações para um novo monitor"""
        try:
            # Enviar contagem de conexões
            await websocket.send_text(json.dumps({
                "type": "connection_count",
                "monitors": len(self.monitors),
                "displays": len(self.displays)
            }))
            
            # Enviar todas as notificações existentes
            for notification in self.notifications.values():
                await websocket.send_text(json.dumps({
                    "type": "notification_sent",
                    "notification_id": notification.id,
                    "child_code": notification.child_code,
                    "status": notification.status.value,
                    "created_at": notification.created_at,
                    "viewed_at": getattr(notification, 'viewed_at', None)
                }))
                
        except Exception as e:
            logger.error(f"Erro ao enviar estado atual: {e}")


    async def broadcast_monitor_count(self):
        """Envia contagem de conexões para todos os monitores"""
        message = json.dumps({
            "type": "connection_count",
            "monitors": len(self.monitors),
            "displays": len(self.displays)
        })
        await self.broadcast_to_monitors(message)

    
    async def send_pending_notifications(self, websocket: WebSocket):
        """Envia todas as notificações pendentes para uma nova conexão"""
        pending = [n for n in self.notifications.values() 
                  if n.status == NotificationStatus.PENDING]
        
        for notification in pending:
            try:
                await websocket.send_text(json.dumps({
                    "type": "new_notification",
                    "notification": notification.model_dump()
                }))
            except Exception as e:
                logger.error(f"Erro ao enviar notificação pendente: {e}")

    
    async def create_notification(self, child_code: str, priority: Priority = Priority.NORMAL, message: Optional[str] = None):
        """Cria uma nova notificação"""
        notification_id = str(uuid.uuid4())
        notification = Notification(
            id=notification_id,
            child_code=child_code,
            priority=priority,
            created_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            message=message
        )
        
        self.notifications[notification_id] = notification
        logger.info(f"Notificação criada: {notification_id} - {child_code}")
        
        # Envia para todos os displays
        message_data = {
            "type": "new_notification",
            "notification": notification.model_dump()
        }
        
        await self.broadcast_to_displays(json.dumps(message_data))
        
        # Confirma para monitores
        await self.broadcast_to_monitors(json.dumps({
            "type": "notification_sent",
            "notification_id": notification_id,
            "child_code": child_code,
            "status": "pending",
            "created_at": notification.created_at
        }))
        
        return notification
    
    
    async def mark_as_viewed(self, notification_id: str):
        """Marca notificação como visualizada"""
        if notification_id in self.notifications:
            self.notifications[notification_id].status = NotificationStatus.VIEWED
            self.notifications[notification_id].viewed_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            logger.info(f"Notificação marcada como vista: {notification_id}")
            
            # Notifica todos os monitores
            await self.broadcast_to_monitors(json.dumps({
                "type": "notification_viewed",
                "notification_id": notification_id,
                "viewed_at": self.notifications[notification_id].viewed_at
            }))
            
            # Remove da tela dos displays
            await self.broadcast_to_displays(json.dumps({
                "type": "notification_removed",
                "notification_id": notification_id
            }))
            
            return True
        return False
    
    
    async def remove_notification(self, notification_id: str):
        """Remove uma notificação manualmente ou por expiração"""
        if notification_id in self.notifications:
            del self.notifications[notification_id]
            logger.info(f"Notificação removida: {notification_id}")
            
            # Notifica monitores para remover da interface
            await self.broadcast_to_monitors(json.dumps({
                "type": "notification_removed",
                "notification_id": notification_id
            }))
            
            return True
        return False

    
    async def broadcast_to_monitors(self, message: str):
        """Envia mensagem para todos os monitores"""
        disconnected = []
        for monitor in self.monitors:
            try:
                await monitor.send_text(message)
            except Exception as e:
                logger.error(f"Erro ao enviar para monitor: {e}")
                disconnected.append(monitor)
        
        # Remove conexões mortas
        for monitor in disconnected:
            self.monitors.remove(monitor)

    
    async def broadcast_to_displays(self, message: str):
        """Envia mensagem para todos os displays"""
        disconnected = []
        for display in self.displays:
            try:
                await display.send_text(message)
            except Exception as e:
                logger.error(f"Erro ao enviar para display: {e}")
                disconnected.append(display)
        
        # Remove conexões mortas
        for display in disconnected:
            self.displays.remove(display)

    
    async def cleanup_old_notifications(self):
        """Remove notificações antigas automaticamente (fallback de segurança)"""
        cutoff_time = datetime.now() - timedelta(minutes=10)
        
        expired_ids = []
        for notification_id, notification in self.notifications.items():
            try:
                created_time = datetime.strptime(notification.created_at, "%d/%m/%Y %H:%M:%S")
                if created_time < cutoff_time:
                    expired_ids.append(notification_id)
            except Exception as e:
                logger.error(f"Erro ao processar data da notificação {notification_id}: {e}")
        
        for notification_id in expired_ids:
            await self.remove_notification(notification_id)
            logger.info(f"Notificação expirada removida: {notification_id}")


# Instância global
manager = ConnectionManager()

# Task para limpeza automática (fallback de segurança)
async def cleanup_task():
    while True:
        await asyncio.sleep(300)  # Executa a cada 5 minutos
        await manager.cleanup_old_notifications()