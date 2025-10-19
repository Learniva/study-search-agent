#!/usr/bin/env python3
"""Test if Stripe Price ID is valid."""

import os
from dotenv import load_dotenv
load_dotenv()
import stripe

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
price_id = os.getenv('STRIPE_PRICE_ID')

print(f'Testing Price ID: {price_id}')
print()

try:
    price = stripe.Price.retrieve(price_id)
    print(f'✅ Price ID is VALID!')
    print(f'   Product: {price.product}')
    print(f'   Amount: ${price.unit_amount/100} {price.currency.upper()}')
    if price.recurring:
        print(f'   Interval: {price.recurring.interval}')
except Exception as e:
    print(f'❌ Price ID is INVALID!')
    print(f'   Error: {e}')
    print()
    print('The Price ID from the Stripe Dashboard was:')
    print('price_1SJs2ZDHHVaKNOBw4REARQG0')
    print()
    print('Please verify this is correct in your Stripe Dashboard.')

