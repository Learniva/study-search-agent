"""Stripe payment integration."""

import os
import stripe
from typing import Optional, Dict, Any
from config.settings import settings

# Initialize Stripe with secret key
stripe.api_key = settings.stripe_secret_key or os.getenv("STRIPE_SECRET_KEY")


def get_stripe_client():
    """Get configured Stripe client."""
    return stripe


stripe_client = get_stripe_client()


async def create_checkout_session(
    customer_email: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    customer_id: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> stripe.checkout.Session:
    """
    Create a Stripe Checkout Session.
    
    Args:
        customer_email: Customer's email address
        price_id: Stripe Price ID for the product
        success_url: URL to redirect on successful payment
        cancel_url: URL to redirect on cancelled payment
        customer_id: Optional existing Stripe customer ID
        metadata: Optional metadata to attach to the session
        
    Returns:
        Stripe Checkout Session object
    """
    session_params = {
        "payment_method_types": ["card"],
        "line_items": [
            {
                "price": price_id,
                "quantity": 1,
            }
        ],
        "mode": "subscription",  # or "payment" for one-time payments
        "success_url": success_url + "?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": cancel_url,
        "customer_email": customer_email if not customer_id else None,
    }
    
    if customer_id:
        session_params["customer"] = customer_id
    
    if metadata:
        session_params["metadata"] = metadata
    
    # Allow promotion codes
    session_params["allow_promotion_codes"] = True
    
    session = stripe.checkout.Session.create(**session_params)
    return session


async def create_customer_portal_session(
    customer_id: str,
    return_url: str,
) -> stripe.billing_portal.Session:
    """
    Create a Stripe Customer Portal Session for managing subscriptions.
    
    Args:
        customer_id: Stripe customer ID
        return_url: URL to return to after portal session
        
    Returns:
        Stripe Customer Portal Session object
    """
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session


async def get_customer(customer_id: str) -> Optional[stripe.Customer]:
    """
    Get Stripe customer by ID.
    
    Args:
        customer_id: Stripe customer ID
        
    Returns:
        Stripe Customer object or None
    """
    try:
        customer = stripe.Customer.retrieve(customer_id)
        return customer
    except stripe.error.StripeError:
        return None


async def create_customer(
    email: str,
    name: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> stripe.Customer:
    """
    Create a new Stripe customer.
    
    Args:
        email: Customer email
        name: Customer name
        metadata: Optional metadata
        
    Returns:
        Stripe Customer object
    """
    customer_params = {"email": email}
    
    if name:
        customer_params["name"] = name
    
    if metadata:
        customer_params["metadata"] = metadata
    
    customer = stripe.Customer.create(**customer_params)
    return customer


async def get_subscription(subscription_id: str) -> Optional[stripe.Subscription]:
    """
    Get Stripe subscription by ID.
    
    Args:
        subscription_id: Stripe subscription ID
        
    Returns:
        Stripe Subscription object or None
    """
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        return subscription
    except stripe.error.StripeError:
        return None


async def cancel_subscription(subscription_id: str) -> stripe.Subscription:
    """
    Cancel a Stripe subscription.
    
    Args:
        subscription_id: Stripe subscription ID
        
    Returns:
        Cancelled Stripe Subscription object
    """
    subscription = stripe.Subscription.modify(
        subscription_id,
        cancel_at_period_end=True,
    )
    return subscription


async def list_customer_subscriptions(customer_id: str) -> list:
    """
    List all subscriptions for a customer.
    
    Args:
        customer_id: Stripe customer ID
        
    Returns:
        List of Stripe Subscription objects
    """
    subscriptions = stripe.Subscription.list(customer=customer_id)
    return subscriptions.data


async def verify_webhook_signature(
    payload: bytes,
    signature: str,
    webhook_secret: str,
) -> Optional[Any]:
    """
    Verify Stripe webhook signature.
    
    Args:
        payload: Raw request payload
        signature: Stripe signature header
        webhook_secret: Webhook signing secret
        
    Returns:
        Verified event object or None
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, webhook_secret
        )
        return event
    except ValueError:
        # Invalid payload
        return None
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return None

