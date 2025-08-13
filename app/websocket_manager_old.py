from fastapi import WebSocket
from typing import List, Dict, Optional
import json
import asyncio
from datetime import datetime, timedelta
from .models import Priority, Notification, NotificationStatus
import uuid

class ConnectionManager:
    def __init__(self):
        # Armazena conexões por tipo (monitor/display)
        self.monitors: List[WebSocket] = []
        self.displays: List[WebSocket] = []
        # Armazena notificações ativas
        self.notifications: Dict[str, Notification] = {}
        

    async def connect_monitor(self, websocket: WebSocket):
        await websocket.accept()
        self.monitors.append(websocket)

        
    async def connect_display(self, websocket: WebSocket):
        await websocket.accept()
        self.displays.append(websocket)
        # Envia notificações pendentes
        await self.send_pending_notifications(websocket)

        
    def disconnect_monitor(self, websocket: WebSocket):
        if websocket in self.monitors:
            self.monitors.remove(websocket)

            
    def disconnect_display(self, websocket: WebSocket):
        if websocket in self.displays:
            self.displays.remove(websocket)

    
    async def send_pending_notifications(self, websocket: WebSocket):
        """Envia todas as notificações pendentes para uma nova conexão"""
        pending = [n for n in self.notifications.values() 
                  if n.status == NotificationStatus.PENDING]
        
        for notification in pending:
            await websocket.send_text(json.dumps({
                "type": "new_notification",
                "notification": notification.model_dump()
            }))

    
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
            "child_code": child_code
        }))
        
        return notification
    
    
    async def mark_as_viewed(self, notification_id: str):
        """Marca notificação como visualizada"""
        if notification_id in self.notifications:
            self.notifications[notification_id].status = NotificationStatus.VIEWED
            self.notifications[notification_id].viewed_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            # Notifica todos os monitores
            await self.broadcast_to_monitors(json.dumps({
                "type": "notification_viewed",
                "notification_id": notification_id
            }))
            
            # Remove da tela dos displays
            await self.broadcast_to_displays(json.dumps({
                "type": "notification_removed",
                "notification_id": notification_id
            }))
            
            return True
        return False
    
    
    async def broadcast_to_monitors(self, message: str):
        """Envia mensagem para todos os monitores"""
        for monitor in self.monitors.copy():
            try:
                await monitor.send_text(message)
            except:
                self.monitors.remove(monitor)

    
    async def broadcast_to_displays(self, message: str):
        """Envia mensagem para todos os displays"""
        for display in self.displays.copy():
            try:
                await display.send_text(message)
            except:
                self.displays.remove(display)

    
    async def cleanup_old_notifications(self):
        """Remove notificações antigas automaticamente"""
        cutoff_time = datetime.now() - timedelta(minutes=5)
        
        expired_ids = []
        for notification_id, notification in self.notifications.items():
            if datetime.strptime(notification.created_at, "%d/%m/%Y %H:%M:%S") < cutoff_time:
                expired_ids.append(notification_id)
        
        for notification_id in expired_ids:
            del self.notifications[notification_id]
            
            # Remove da tela se ainda estava pendente
            await self.broadcast_to_displays(json.dumps({
                "type": "notification_removed",
                "notification_id": notification_id
            }))


# Instância global
manager = ConnectionManager()

# Task para limpeza automática
async def cleanup_task():
    while True:
        await asyncio.sleep(60)  # Executa a cada minuto
        await manager.cleanup_old_notifications()