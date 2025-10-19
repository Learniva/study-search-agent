"""Payment endpoints for Stripe integration."""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Request, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from utils.payment import (
    create_checkout_session,
    create_customer_portal_session,
    get_customer,
    create_customer,
    verify_webhook_signature,
)
from database.core.async_engine import get_async_db
from database.models.payment import Customer, Subscription, PaymentHistory, SubscriptionStatus
from sqlalchemy import select
from datetime import datetime

router = APIRouter(prefix="/payments", tags=["payments"])

# Load Stripe configuration from settings
from config.settings import settings

STRIPE_PUBLISHABLE_KEY = settings.stripe_publishable_key or os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_PRICE_ID = settings.stripe_price_id or os.getenv("STRIPE_PRICE_ID", "")
STRIPE_SUCCESS_URL = settings.stripe_success_url or os.getenv("STRIPE_SUCCESS_URL", "http://localhost:3000/payment/success")
STRIPE_CANCEL_URL = settings.stripe_cancel_url or os.getenv("STRIPE_CANCEL_URL", "http://localhost:3000/payment/cancel")
STRIPE_WEBHOOK_SECRET = settings.stripe_webhook_secret or os.getenv("STRIPE_WEBHOOK_SECRET", "")


class CheckoutSessionRequest(BaseModel):
    """Request model for creating a checkout session."""
    user_id: str
    email: EmailStr
    price_id: Optional[str] = None
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CheckoutSessionResponse(BaseModel):
    """Response model for checkout session."""
    session_id: str
    url: str
    publishable_key: str


class CustomerPortalRequest(BaseModel):
    """Request model for customer portal."""
    user_id: str
    return_url: Optional[str] = None


class CustomerPortalResponse(BaseModel):
    """Response model for customer portal."""
    url: str


class SubscriptionResponse(BaseModel):
    """Response model for subscription."""
    subscription_id: str
    status: str
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout(
    request: CheckoutSessionRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a Stripe Checkout Session for subscription.
    
    Args:
        request: Checkout session request with user info
        db: Database session
        
    Returns:
        Checkout session with URL and publishable key
    """
    try:
        # Validate Stripe configuration
        if not STRIPE_PUBLISHABLE_KEY or STRIPE_PUBLISHABLE_KEY == "":
            raise HTTPException(
                status_code=500, 
                detail="Stripe publishable key not configured. Please set STRIPE_PUBLISHABLE_KEY in your environment variables."
            )
        
        # Check if customer already exists
        result = await db.execute(
            select(Customer).where(Customer.user_id == request.user_id)
        )
        existing_customer = result.scalar_one_or_none()
        
        customer_id = None
        if existing_customer:
            customer_id = existing_customer.stripe_customer_id
        
        # Use provided price_id or default
        price_id = request.price_id or STRIPE_PRICE_ID
        if not price_id or price_id in ["", "price_your_price_id_here"]:
            raise HTTPException(
                status_code=400, 
                detail="No valid Stripe Price ID configured. Please create a product in Stripe Dashboard and set STRIPE_PRICE_ID in your .env file."
            )
        
        # Create checkout session
        session = await create_checkout_session(
            customer_email=request.email,
            price_id=price_id,
            success_url=request.success_url or STRIPE_SUCCESS_URL,
            cancel_url=request.cancel_url or STRIPE_CANCEL_URL,
            customer_id=customer_id,
            metadata={"user_id": request.user_id},
        )
        
        return CheckoutSessionResponse(
            session_id=session.id,
            url=session.url,
            publishable_key=STRIPE_PUBLISHABLE_KEY,
        )
    except HTTPException:
        raise
    except Exception as e:
        # Log the full error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Stripe checkout error: {type(e).__name__}: {str(e)}")
        
        # Provide user-friendly error message
        error_msg = str(e)
        if "No such price" in error_msg:
            error_msg = "Invalid Stripe Price ID. Please check your STRIPE_PRICE_ID configuration."
        elif "Invalid API Key" in error_msg or "api_key" in error_msg.lower():
            error_msg = "Invalid Stripe API key. Please check your STRIPE_SECRET_KEY configuration."
        
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/create-customer-portal", response_model=CustomerPortalResponse)
async def create_portal(
    request: CustomerPortalRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a Stripe Customer Portal Session for managing subscriptions.
    
    Args:
        request: Customer portal request
        db: Database session
        
    Returns:
        Customer portal URL
    """
    try:
        # Get customer from database
        result = await db.execute(
            select(Customer).where(Customer.user_id == request.user_id)
        )
        customer = result.scalar_one_or_none()
        
        if not customer:
            raise HTTPException(
                status_code=404, 
                detail="No Stripe customer found. You need to subscribe first before you can manage your subscription."
            )
        
        # Create customer portal session
        session = await create_customer_portal_session(
            customer_id=customer.stripe_customer_id,
            return_url=request.return_url or STRIPE_SUCCESS_URL,
        )
        
        return CustomerPortalResponse(url=session.url)
    except HTTPException:
        raise
    except Exception as e:
        # Log the full error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Stripe portal error: {type(e).__name__}: {str(e)}")
        
        # Provide user-friendly error message
        error_msg = str(e)
        if "No such customer" in error_msg:
            error_msg = "Customer not found in Stripe. Please contact support."
        elif "Invalid API Key" in error_msg or "api_key" in error_msg.lower():
            error_msg = "Invalid Stripe API key. Please check your configuration."
        
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/subscription/{user_id}", response_model=SubscriptionResponse)
async def get_subscription_status(
    user_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get user's subscription status.
    
    Args:
        user_id: User ID
        db: Database session
        
    Returns:
        Subscription information
    """
    try:
        # Get active subscription
        result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .where(Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]))
            .order_by(Subscription.created_at.desc())
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            raise HTTPException(status_code=404, detail="No active subscription found")
        
        return SubscriptionResponse(
            subscription_id=subscription.stripe_subscription_id,
            status=subscription.status.value,
            current_period_end=subscription.current_period_end,
            cancel_at_period_end=subscription.cancel_at_period_end,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Handle Stripe webhook events.
    
    Args:
        request: FastAPI request
        stripe_signature: Stripe signature header
        db: Database session
        
    Returns:
        Success response
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")
    
    payload = await request.body()
    
    # Verify webhook signature
    event = await verify_webhook_signature(
        payload=payload,
        signature=stripe_signature,
        webhook_secret=STRIPE_WEBHOOK_SECRET,
    )
    
    if not event:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle different event types
    event_type = event["type"]
    
    try:
        if event_type == "checkout.session.completed":
            await handle_checkout_completed(event, db)
        elif event_type == "customer.subscription.created":
            await handle_subscription_created(event, db)
        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(event, db)
        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(event, db)
        elif event_type == "invoice.payment_succeeded":
            await handle_payment_succeeded(event, db)
        elif event_type == "invoice.payment_failed":
            await handle_payment_failed(event, db)
        
        return {"status": "success"}
    except Exception as e:
        print(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def handle_checkout_completed(event: dict, db: AsyncSession):
    """Handle checkout.session.completed event."""
    session = event["data"]["object"]
    customer_id = session["customer"]
    customer_email = session["customer_details"]["email"]
    user_id = session["metadata"].get("user_id")
    
    if not user_id:
        return
    
    # Create or update customer in database
    result = await db.execute(
        select(Customer).where(Customer.user_id == user_id)
    )
    existing_customer = result.scalar_one_or_none()
    
    if not existing_customer:
        new_customer = Customer(
            user_id=user_id,
            stripe_customer_id=customer_id,
            email=customer_email,
        )
        db.add(new_customer)
        await db.commit()


async def handle_subscription_created(event: dict, db: AsyncSession):
    """Handle customer.subscription.created event."""
    subscription = event["data"]["object"]
    
    # Find customer
    result = await db.execute(
        select(Customer).where(Customer.stripe_customer_id == subscription["customer"])
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        return
    
    # Create subscription record
    new_subscription = Subscription(
        user_id=customer.user_id,
        stripe_subscription_id=subscription["id"],
        stripe_customer_id=subscription["customer"],
        status=SubscriptionStatus(subscription["status"]),
        price_id=subscription["items"]["data"][0]["price"]["id"],
        current_period_start=datetime.fromtimestamp(subscription["current_period_start"]),
        current_period_end=datetime.fromtimestamp(subscription["current_period_end"]),
        cancel_at_period_end=subscription["cancel_at_period_end"],
    )
    db.add(new_subscription)
    await db.commit()


async def handle_subscription_updated(event: dict, db: AsyncSession):
    """Handle customer.subscription.updated event."""
    subscription = event["data"]["object"]
    
    # Update subscription in database
    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == subscription["id"]
        )
    )
    db_subscription = result.scalar_one_or_none()
    
    if db_subscription:
        db_subscription.status = SubscriptionStatus(subscription["status"])
        db_subscription.current_period_start = datetime.fromtimestamp(subscription["current_period_start"])
        db_subscription.current_period_end = datetime.fromtimestamp(subscription["current_period_end"])
        db_subscription.cancel_at_period_end = subscription["cancel_at_period_end"]
        
        if subscription.get("canceled_at"):
            db_subscription.canceled_at = datetime.fromtimestamp(subscription["canceled_at"])
        
        await db.commit()


async def handle_subscription_deleted(event: dict, db: AsyncSession):
    """Handle customer.subscription.deleted event."""
    subscription = event["data"]["object"]
    
    # Update subscription status in database
    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == subscription["id"]
        )
    )
    db_subscription = result.scalar_one_or_none()
    
    if db_subscription:
        db_subscription.status = SubscriptionStatus.CANCELED
        db_subscription.canceled_at = datetime.utcnow()
        await db.commit()


async def handle_payment_succeeded(event: dict, db: AsyncSession):
    """Handle invoice.payment_succeeded event."""
    invoice = event["data"]["object"]
    payment_intent = invoice["payment_intent"]
    
    # Find customer
    result = await db.execute(
        select(Customer).where(Customer.stripe_customer_id == invoice["customer"])
    )
    customer = result.scalar_one_or_none()
    
    if not customer or not payment_intent:
        return
    
    # Record payment
    payment = PaymentHistory(
        user_id=customer.user_id,
        stripe_payment_intent_id=payment_intent,
        stripe_customer_id=invoice["customer"],
        amount=invoice["amount_paid"],
        currency=invoice["currency"],
        status="succeeded",
        description=invoice.get("description", ""),
    )
    db.add(payment)
    await db.commit()


async def handle_payment_failed(event: dict, db: AsyncSession):
    """Handle invoice.payment_failed event."""
    invoice = event["data"]["object"]
    
    # You can add logic here to notify the user or take action on failed payments
    print(f"Payment failed for customer: {invoice['customer']}")


@router.get("/config")
async def get_stripe_config():
    """Get Stripe publishable key and configuration."""
    return {
        "publishable_key": STRIPE_PUBLISHABLE_KEY,
        "price_id": STRIPE_PRICE_ID,
    }

