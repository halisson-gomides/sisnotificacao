from pydantic import BaseModel
from enum import Enum
from typing import Optional

class Priority(str, Enum):
    NORMAL = "normal"
    URGENT = "urgente"

class NotificationStatus(str, Enum):
    PENDING = "pendente"
    VIEWED = "visto"
    EXPIRED = "expirado"

class Notification(BaseModel):
    id: str
    child_code: str
    priority: Priority = Priority.NORMAL
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: str
    viewed_at: Optional[str] = None
    message: Optional[str] = None
