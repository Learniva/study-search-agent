"""
Help & Support Router

Endpoints for user help and support including:
- FAQ retrieval
- Support ticket submission
- Community access
- Documentation links
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from utils.auth.jwt_handler import get_current_user  # Use Google OAuth JWT authentication

router = APIRouter(prefix="/api/help", tags=["help"])


# ============================================================================
# Models
# ============================================================================

class FAQItem(BaseModel):
    """FAQ item model."""
    id: int
    question: str
    answer: str
    category: str
    helpful_count: int = 0


class FAQCategory(BaseModel):
    """FAQ category model."""
    name: str
    items: List[FAQItem]


class SupportTicketRequest(BaseModel):
    """Support ticket request."""
    subject: str
    message: str
    category: str
    priority: str = "normal"  # low, normal, high, urgent


class SupportTicketResponse(BaseModel):
    """Support ticket response."""
    ticket_id: str
    subject: str
    status: str
    created_at: datetime
    last_updated: datetime


class ContactRequest(BaseModel):
    """Contact form request."""
    name: str
    email: EmailStr
    subject: str
    message: str


# ============================================================================
# FAQ Data (In production, store in database)
# ============================================================================

FAQ_DATA = [
    {
        "id": 1,
        "question": "How do I create a new workspace?",
        "answer": "To create a new workspace, click on the 'Workspaces' dropdown in the sidebar and select 'Create New Workspace'. Enter a name and description for your workspace, then click 'Create'.",
        "category": "Workspaces",
        "helpful_count": 45
    },
    {
        "id": 2,
        "question": "Can I attach documents to my conversations?",
        "answer": "Yes! You can attach documents by clicking the paperclip icon in the chat input. Supported formats include PDF, DOCX, TXT, and more. The AI will analyze the document and answer questions about it.",
        "category": "Documents",
        "helpful_count": 82
    },
    {
        "id": 3,
        "question": "How do I generate animations?",
        "answer": "To generate animations, ask the AI to create a visualization or animation of a concept. For example: 'Create an animation explaining neural networks'. The AI will generate a video using the Manim engine.",
        "category": "Animations",
        "helpful_count": 67
    },
    {
        "id": 4,
        "question": "What file formats are supported?",
        "answer": "Learniva supports various file formats including PDF, DOCX, TXT, MD, CSV, XLSX, and more. For code files, we support Python, JavaScript, Java, C++, and many other programming languages.",
        "category": "Documents",
        "helpful_count": 38
    },
    {
        "id": 5,
        "question": "How do I switch between light and dark mode?",
        "answer": "Go to Settings > Appearance > Theme and select 'Light', 'Dark', or 'System' to match your system preferences.",
        "category": "Settings",
        "helpful_count": 25
    },
    {
        "id": 6,
        "question": "Can I delete my workspaces?",
        "answer": "Yes, you can delete a workspace by opening the workspace settings (three dots menu) and selecting 'Delete Workspace'. Note that this action is permanent and cannot be undone.",
        "category": "Workspaces",
        "helpful_count": 19
    },
    {
        "id": 7,
        "question": "How do I upgrade to Premium?",
        "answer": "To upgrade to Premium, go to Account Settings > Billing and click the 'Upgrade' button on the Premium plan. You'll be redirected to our secure payment page to complete the purchase.",
        "category": "Billing",
        "helpful_count": 56
    },
    {
        "id": 8,
        "question": "What's the difference between Basic and Premium?",
        "answer": "Premium offers unlimited journals & chats, 5 video generations per day, 5 flashcard generations per day, 30-day version history, and priority support. Basic plan has limited features suitable for casual users.",
        "category": "Billing",
        "helpful_count": 91
    },
    {
        "id": 9,
        "question": "How do I change my password?",
        "answer": "Go to Account Settings > Security > Password and enter your current password, new password, and confirm the new password. Click 'Update' to save your changes.",
        "category": "Security",
        "helpful_count": 14
    },
    {
        "id": 10,
        "question": "Can I export my data?",
        "answer": "Yes, you can export your workspace data including notes, conversations, and documents. Go to Workspace Settings and click 'Export Data'. Your data will be prepared as a downloadable ZIP file.",
        "category": "Data",
        "helpful_count": 32
    }
]


# ============================================================================
# Endpoints - FAQ
# ============================================================================

@router.get("/faq")
async def get_faq(category: Optional[str] = None):
    """
    Get FAQ items, optionally filtered by category.
    
    Query Parameters:
        category: Optional category filter (Workspaces, Documents, Animations, etc.)
    
    Response:
        {
            "items": [...],
            "categories": ["Workspaces", "Documents", ...]
        }
    """
    faq_items = FAQ_DATA
    
    # Filter by category if provided
    if category:
        faq_items = [item for item in faq_items if item["category"].lower() == category.lower()]
    
    # Get unique categories
    categories = sorted(list(set(item["category"] for item in FAQ_DATA)))
    
    return {
        "items": faq_items,
        "categories": categories,
        "total": len(faq_items)
    }


@router.get("/faq/categories")
async def get_faq_by_categories():
    """
    Get FAQ items grouped by categories.
    
    Response:
        {
            "Workspaces": [...],
            "Documents": [...],
            ...
        }
    """
    # Group FAQ items by category
    categories = {}
    for item in FAQ_DATA:
        category = item["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(item)
    
    return categories


@router.get("/faq/{faq_id}")
async def get_faq_item(faq_id: int):
    """
    Get a specific FAQ item by ID.
    
    Path Parameters:
        faq_id: FAQ item ID
    
    Response:
        {
            "id": 1,
            "question": "...",
            "answer": "...",
            "category": "...",
            "helpful_count": 45
        }
    """
    faq_item = next((item for item in FAQ_DATA if item["id"] == faq_id), None)
    
    if not faq_item:
        raise HTTPException(
            status_code=404,
            detail="FAQ item not found"
        )
    
    return faq_item


@router.post("/faq/{faq_id}/helpful")
async def mark_faq_helpful(faq_id: int, current_user: dict = Depends(get_current_user)):
    """
    Mark an FAQ item as helpful.
    
    Headers:
        Authorization: Token abc123...
    
    Path Parameters:
        faq_id: FAQ item ID
    
    Response:
        {
            "message": "Thank you for your feedback",
            "helpful_count": 46
        }
    """
    faq_item = next((item for item in FAQ_DATA if item["id"] == faq_id), None)
    
    if not faq_item:
        raise HTTPException(
            status_code=404,
            detail="FAQ item not found"
        )
    
    # Increment helpful count
    faq_item["helpful_count"] += 1
    
    return {
        "message": "Thank you for your feedback",
        "helpful_count": faq_item["helpful_count"]
    }


# ============================================================================
# Endpoints - Support Tickets
# ============================================================================

# In-memory storage for demo (use database in production)
SUPPORT_TICKETS = {}
TICKET_COUNTER = 0


@router.post("/support/ticket")
async def create_support_ticket(
    ticket: SupportTicketRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new support ticket.
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "subject": "Issue with video generation",
            "message": "I'm experiencing problems...",
            "category": "technical",
            "priority": "normal"
        }
    
    Response:
        {
            "ticket_id": "TICKET-001",
            "subject": "Issue with video generation",
            "status": "open",
            "created_at": "2025-10-17T10:30:00Z",
            "last_updated": "2025-10-17T10:30:00Z"
        }
    """
    global TICKET_COUNTER
    TICKET_COUNTER += 1
    
    ticket_id = f"TICKET-{TICKET_COUNTER:03d}"
    now = datetime.utcnow()
    
    ticket_data = {
        "ticket_id": ticket_id,
        "user_id": current_user["id"],
        "user_email": current_user["email"],
        "subject": ticket.subject,
        "message": ticket.message,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": "open",
        "created_at": now,
        "last_updated": now
    }
    
    SUPPORT_TICKETS[ticket_id] = ticket_data
    
    return SupportTicketResponse(
        ticket_id=ticket_id,
        subject=ticket.subject,
        status="open",
        created_at=now,
        last_updated=now
    )


@router.get("/support/tickets")
async def get_user_tickets(current_user: dict = Depends(get_current_user)):
    """
    Get all support tickets for the current user.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "tickets": [
                {
                    "ticket_id": "TICKET-001",
                    "subject": "...",
                    "status": "open",
                    "created_at": "...",
                    "last_updated": "..."
                }
            ],
            "total": 1
        }
    """
    user_tickets = [
        SupportTicketResponse(
            ticket_id=ticket["ticket_id"],
            subject=ticket["subject"],
            status=ticket["status"],
            created_at=ticket["created_at"],
            last_updated=ticket["last_updated"]
        )
        for ticket in SUPPORT_TICKETS.values()
        if ticket["user_id"] == current_user["id"]
    ]
    
    return {
        "tickets": user_tickets,
        "total": len(user_tickets)
    }


@router.get("/support/tickets/{ticket_id}")
async def get_ticket_details(
    ticket_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get details of a specific support ticket.
    
    Headers:
        Authorization: Token abc123...
    
    Path Parameters:
        ticket_id: Support ticket ID
    
    Response:
        Complete ticket details including messages
    """
    ticket = SUPPORT_TICKETS.get(ticket_id)
    
    if not ticket:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )
    
    # Verify ownership
    if ticket["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to view this ticket"
        )
    
    return ticket


# ============================================================================
# Endpoints - Contact
# ============================================================================

@router.post("/contact")
async def submit_contact_form(contact: ContactRequest):
    """
    Submit a contact form (public endpoint, no auth required).
    
    Request Body:
        {
            "name": "John Doe",
            "email": "john@example.com",
            "subject": "Question about Premium plan",
            "message": "I would like to know..."
        }
    
    Response:
        {
            "message": "Thank you for contacting us. We'll get back to you soon.",
            "reference_id": "CONTACT-001"
        }
    """
    # In production, send email to support team or create ticket
    global TICKET_COUNTER
    TICKET_COUNTER += 1
    reference_id = f"CONTACT-{TICKET_COUNTER:03d}"
    
    return {
        "message": "Thank you for contacting us. We'll get back to you soon.",
        "reference_id": reference_id
    }


# ============================================================================
# Endpoints - Documentation & Resources
# ============================================================================

@router.get("/resources")
async def get_resources():
    """
    Get links to documentation and learning resources.
    
    Response:
        {
            "documentation": [...],
            "tutorials": [...],
            "community": {...}
        }
    """
    return {
        "documentation": [
            {
                "title": "Getting Started Guide",
                "url": "/docs/getting-started",
                "description": "Learn the basics of using Learniva"
            },
            {
                "title": "Document Upload Guide",
                "url": "/docs/documents",
                "description": "How to upload and manage your documents"
            },
            {
                "title": "Animation Generation",
                "url": "/docs/animations",
                "description": "Create educational animations with AI"
            },
            {
                "title": "API Documentation",
                "url": "/docs/api",
                "description": "Integrate Learniva with your applications"
            }
        ],
        "tutorials": [
            {
                "title": "Create Your First Workspace",
                "url": "/tutorials/first-workspace",
                "duration": "5 min",
                "difficulty": "beginner"
            },
            {
                "title": "Master Document Q&A",
                "url": "/tutorials/document-qa",
                "duration": "10 min",
                "difficulty": "beginner"
            },
            {
                "title": "Generate Study Materials",
                "url": "/tutorials/study-materials",
                "duration": "15 min",
                "difficulty": "intermediate"
            }
        ],
        "community": {
            "discord": "https://discord.gg/learniva",
            "forum": "https://community.learniva.ai",
            "twitter": "https://twitter.com/learnivaai",
            "blog": "https://blog.learniva.ai"
        },
        "support": {
            "email": "support@learniva.ai",
            "response_time": "24 hours",
            "availability": "Monday - Friday, 9 AM - 5 PM EST"
        }
    }


@router.get("/changelog")
async def get_changelog():
    """
    Get recent product updates and changes.
    
    Response:
        {
            "updates": [...]
        }
    """
    return {
        "updates": [
            {
                "version": "2.0.0",
                "date": "2025-10-15",
                "title": "Major Platform Update",
                "changes": [
                    "New animation generation engine with better quality",
                    "Improved document processing with better accuracy",
                    "Enhanced AI responses with GPT-4 integration",
                    "New workspace collaboration features",
                    "Performance improvements and bug fixes"
                ]
            },
            {
                "version": "1.9.5",
                "date": "2025-10-01",
                "title": "Bug Fixes and Improvements",
                "changes": [
                    "Fixed issue with large document uploads",
                    "Improved video generation stability",
                    "Updated UI components for better accessibility",
                    "Minor bug fixes"
                ]
            }
        ]
    }

