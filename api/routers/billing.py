"""
Billing Router

Handles billing, subscription, and payment information.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List

from utils.auth.jwt_handler import get_current_user  # Use Google OAuth JWT authentication

router = APIRouter(prefix="/api/billing", tags=["billing"])


class PlanInformation(BaseModel):
    """Plan information model."""
    name: str
    tier: str
    price: float
    currency: str
    status: str
    features: List[str]


class BillingResponse(BaseModel):
    """Billing response model."""
    current_plan: PlanInformation
    available_plans: List[dict]
    payment_method: Optional[dict]
    next_billing_date: Optional[str]
    billing_required: bool


@router.get("/plans/")
@router.get("/plans")
async def get_billing_plans(current_user: dict = Depends(get_current_user)):
    """
    Get available billing plans.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        List of available plans with pricing and features
    """
    plans = [
        {
            "id": "free",
            "name": "Basic",
            "tier": "free",
            "price": 0.0,
            "currency": "USD",
            "billing_cycle": "forever",
            "features": [
                "Limited image and video generations",
                "Limited interactive flashcards",
                "Limited practice generations",
                "Limited chats and document search",
                "Basic support"
            ]
        },
        {
            "id": "premium",
            "name": "Premium",
            "tier": "premium",
            "price": 9.99,
            "currency": "USD",
            "billing_cycle": "monthly",
            "features": [
                "AI-Powered Study Tools",
                "Mind maps, notes, and more",
                "Unlimited journals & chats",
                "5 video generations / day",
                "5 flashcard generations / day",
                "30 day version history",
                "Priority support"
            ]
        },
        {
            "id": "pro",
            "name": "Pro",
            "tier": "pro",
            "price": 19.99,
            "currency": "USD",
            "billing_cycle": "monthly",
            "features": [
                "Everything in Premium",
                "Unlimited video generations",
                "Unlimited flashcard generations",
                "Advanced AI features",
                "Team collaboration",
                "API access",
                "Dedicated support"
            ]
        }
    ]
    
    return {"plans": plans}


@router.get("/")
@router.get("")
async def get_billing_info(current_user: dict = Depends(get_current_user)):
    """
    Get user's billing information and current plan.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "current_plan": {
                "name": "Basic",
                "tier": "free",
                "price": 0.0,
                "currency": "USD",
                "status": "active",
                "features": [...]
            },
            "payment_method": null,
            "next_billing_date": null,
            "billing_required": false
        }
    """
    # Default to Basic (free) plan
    current_plan = PlanInformation(
        name="Basic",
        tier="free",
        price=0.0,
        currency="USD",
        status="active",
        features=[
            "Limited image and video generations",
            "Limited interactive flashcards",
            "Limited practice generations",
            "Limited chats and document search",
            "Basic support"
        ]
    )
    
    available_plans = [
        {
            "name": "Basic",
            "tier": "free",
            "price": 0.0,
            "currency": "USD",
            "features": [
                "Limited image and video generations",
                "Limited interactive flashcards",
                "Limited practice generations",
                "Limited chats and document search",
                "Basic support"
            ]
        },
        {
            "name": "Premium",
            "tier": "premium",
            "price": 9.99,
            "currency": "USD",
            "features": [
                "AI-Powered Study Tools",
                "Mind maps, notes, and more",
                "Unlimited journals & chats",
                "5 video generations / day",
                "5 flashcard generations / day",
                "30 day version history",
                "Priority support"
            ]
        },
        {
            "name": "Pro",
            "tier": "pro",
            "price": 19.99,
            "currency": "USD",
            "features": [
                "Everything in Premium",
                "Unlimited video generations",
                "Unlimited flashcard generations",
                "Advanced analytics",
                "API access",
                "Custom integrations",
                "Dedicated support"
            ]
        }
    ]
    
    return {
        "current_plan": current_plan.dict(),
        "available_plans": available_plans,
        "payment_method": None,
        "next_billing_date": None,
        "billing_required": False
    }


@router.post("/upgrade")
async def upgrade_plan(
    plan_tier: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Upgrade user's subscription plan.
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "plan_tier": "premium"
        }
    
    Response:
        {
            "message": "Plan upgrade initiated",
            "plan": "premium",
            "checkout_url": "https://stripe.com/checkout/..."
        }
    """
    # In production, integrate with payment gateway (Stripe, PayPal, etc.)
    return {
        "message": "Plan upgrade initiated (not implemented)",
        "plan": plan_tier,
        "checkout_url": None,
        "status": "pending_payment"
    }


@router.post("/downgrade")
async def downgrade_plan(
    plan_tier: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Downgrade user's subscription plan.
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "plan_tier": "free"
        }
    
    Response:
        {
            "message": "Plan downgrade scheduled",
            "plan": "free",
            "effective_date": "2025-11-01"
        }
    """
    return {
        "message": "Plan downgrade scheduled (not implemented)",
        "plan": plan_tier,
        "effective_date": "2025-11-01",
        "status": "scheduled"
    }


@router.post("/cancel")
async def cancel_subscription(current_user: dict = Depends(get_current_user)):
    """
    Cancel user's subscription.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "message": "Subscription cancelled",
            "effective_date": "2025-11-01"
        }
    """
    return {
        "message": "Subscription cancellation scheduled (not implemented)",
        "effective_date": "2025-11-01",
        "status": "scheduled"
    }


@router.get("/history")
async def get_billing_history(current_user: dict = Depends(get_current_user)):
    """
    Get user's billing history.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "invoices": [],
            "transactions": []
        }
    """
    return {
        "invoices": [],
        "transactions": []
    }


@router.post("/payment-method")
async def add_payment_method(
    payment_method: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Add payment method.
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "type": "card",
            "card_number": "****1234",
            "expiry": "12/25"
        }
    
    Response:
        {
            "message": "Payment method added",
            "payment_method_id": "pm_123"
        }
    """
    return {
        "message": "Payment method addition not implemented",
        "payment_method_id": None
    }

