from typing import Optional
from support.models import SupportTicket, ChatSession
from django.contrib.auth import get_user_model

User = get_user_model()


class TicketService:
    @staticmethod
    def auto_create_ticket(session: ChatSession, description: str) -> SupportTicket:
        """
        Automatically creates a support ticket linked to a chat session.
        """
        desc_lower = description.lower()
        priority = 'medium'
        
        # Escalate priority for urgent keywords
        if any(w in desc_lower for w in ('urgent', 'tezkor', 'muhim', 'critical', 'avariya', 'ishlamayapti')):
            priority = 'high'

        title = f"Avtomatik chipta (Sessiya: {str(session.session_id)[:8]})"
        
        ticket = SupportTicket.objects.create(
            session=session,
            user=session.user,
            organization_id=session.organization_id,
            branch_id=session.branch_id,
            title=title,
            description=description,
            status='open',
            priority=priority
        )
        return ticket
  
    @staticmethod
    def create_user_ticket(
        user, 
        organization_id: int, 
        title: str, 
        description: str, 
        priority: str = 'medium',
        branch_id: Optional[int] = None,
        email: Optional[str] = None
    ) -> SupportTicket:
        """
        Allows users or guests to create a ticket manually.
        """
        # Resolve user
        ticket_user = user if user and user.is_authenticated else None
        
        ticket = SupportTicket.objects.create(
            user=ticket_user,
            email=email,
            organization_id=organization_id,
            branch_id=branch_id,
            title=title,
            description=description,
            status='open',
            priority=priority
        )
        return ticket
