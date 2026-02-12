# VyaparAI Customer Experience Guide

## Overview

This document covers the customer-facing features and user experience flows in VyaparAI, including authentication, store discovery, shopping, cart management, and checkout.

**Last Updated**: February 11, 2026
**Status**: Production-ready features documented

---

## Table of Contents

1. [Authentication Flow](#authentication-flow)
2. [Store Discovery](#store-discovery)
3. [Shopping Experience](#shopping-experience)
4. [Cart Management](#cart-management)
5. [Profile Management](#profile-management)
6. [Checkout Process](#checkout-process)
7. [Guest Checkout Flow](#guest-checkout-flow)
8. [November 2025 UX Enhancements](#november-2025-ux-enhancements)

---

## Authentication Flow

### OTP-Based Phone Authentication

VyaparAI uses passwordless OTP (One-Time Password) authentication for security and ease of use.

**Flow**:
1. **Phone Entry** - Customer enters mobile number (+91 prefix)
2. **OTP Sent** - 6-digit OTP sent via SMS
3. **OTP Verification** - Customer enters OTP code
4. **New Customer Detection** - If phone not found, shows registration
5. **Profile Completion** - Optional additional details

### Implementation Details

**Component**: `/frontend-pwa/src/pages/CustomerAuth.tsx`

**Key Features**:
- Phone validation (10-digit Indian numbers)
- 60-second OTP resend cooldown
- Automatic +91 prefix formatting
- Guest cart migration after auth
- Progressive profile completion

**User States**:
- **Guest** - Browsing without authentication
- **Authenticated** - Logged in via OTP
- **Profile Complete** - All optional fields filled

### Guest Cart Migration

When a customer authenticates after browsing as guest:

```typescript
// Save guest session ID before login
const guestSessionId = sessionManager.getGuestSessionId();

// After OTP verification
if (guestSessionId) {
  await migrateGuestCart(guestSessionId);
  // Guest cart items transferred to authenticated cart
}
```

**Benefits**:
- No lost items when logging in
- Seamless transition from guest to authenticated
- Single cart experience

---

## Store Discovery

### Dual Search Methods

#### 1. GPS-Based Search (Recommended)

**Component**: `/frontend-pwa/src/pages/NearbyStoresEnhanced.tsx`

**Flow**:
1. Request location permission
2. Get current coordinates
3. Query stores within delivery radius
4. Display with distance and delivery time

**Features**:
- Real-time distance calculation
- Sort by distance
- Filter by store type
- Show delivery radius on map

**API**: `GET /api/v1/stores/nearby?lat={lat}&lng={lng}&radius={km}`

#### 2. Manual Search (Fallback)

**Search Methods**:
- **City + State Dropdowns** - Hierarchical selection
- **Pincode Search** - Direct 6-digit pincode entry
- **Landmark Search** - Search by famous landmarks

**Use Cases**:
- Location permission denied
- GPS unavailable or inaccurate
- Searching for stores in different city

**Component**: `/frontend-pwa/src/components/customer/StoreSearch.tsx`

### Store Profile Pages

**Enhanced Store Pages** (November 2025):
- Store story and history
- Owner biography with photos
- Photo gallery and videos
- Community impact metrics
- Certifications and awards
- Customer reviews

**Component**: `/frontend-pwa/src/pages/customer/EnhancedStoreHomePage.tsx`

---

## Shopping Experience

### Product Catalog

**Features**:
- Category-based browsing
- Multi-language product names (10+ languages)
- Product images with gallery view
- Price and availability display
- Add to cart directly from catalog

### Product Detail View

**Component**: `/frontend-pwa/src/components/customer/ProductDetailDialog.tsx`

**Information Displayed**:
- Product name and description
- Brand and manufacturer
- Price, MRP, and discount
- Size, unit, and packaging
- Nutrition information (if applicable)
- Ingredients list
- Multiple product images with zoom
- Stock availability

**Image Gallery**:
- Responsive carousel
- Thumbnail navigation
- Lightbox modal for full-size
- Touch gestures for mobile
- Keyboard navigation
- Lazy loading

**Component**: `/frontend-pwa/src/components/customer/ProductImageGallery.tsx`

### Search and Filters

**Search Capabilities**:
- Text search across product names
- Category filters
- Brand filters
- Price range filters
- Sort options (price, popularity, name)

**Multi-Language Search**:
- Search in any supported language
- Automatic translation to English
- Regional name matching

---

## Cart Management

### Cart Features

**Component**: `/frontend-pwa/src/stores/cartStore.ts`

**Core Capabilities**:
- Add/remove items
- Update quantities
- Real-time price calculation
- Apply discounts
- Save for later
- Cart sharing (multi-device sync for authenticated users)

### Cart TTL (Time-To-Live)

**November 2025 Enhancement**: 30-day cart expiration with countdown

**Implementation**:
- Cart items expire after 30 days of inactivity
- Countdown timer shows remaining time
- Warning before expiration
- Automatic cleanup of expired items

**Component**: `/frontend-pwa/src/hooks/useCartWithEdgeCases.ts`

**User Experience**:
```
Cart Status: 28 days remaining
[Progress Bar ████████░░░░░░░░░░░░]

Items will be removed in 2 days
[Renew Cart Button]
```

### Cart Persistence

**Guest Cart**:
- Stored in LocalStorage
- Persists across sessions
- Session ID: `guest_session_{uuid}`

**Authenticated Cart**:
- Stored in backend (DynamoDB/PostgreSQL)
- Synced across devices
- Survives app uninstall/reinstall

### Cart Migration

When guest authenticates:
1. Backend API: `POST /api/v1/cart/migrate`
2. Guest cart items transferred to user cart
3. Duplicate items merged (quantities added)
4. Guest cart cleared

---

## Profile Management

### Profile Completion Flow

**Philosophy**: Encourage, don't mandate

**Required Fields** (for authentication only):
- Phone number
- First name
- Last name

**Optional Fields** (progressive disclosure):
- Email address
- Date of birth
- Gender
- Profile picture
- Addresses (multiple)
- Payment methods

**Component**: `/frontend-pwa/src/pages/CustomerAccountDashboard.tsx`

**Completion Incentives**:
- Progress bar showing % complete
- Benefits of complete profile:
  - Faster checkout
  - Personalized recommendations
  - Birthday discounts
  - Order tracking via email
- Gentle prompts (not blocking)

**Profile Sections**:
1. **Personal Information**
   - Name, email, phone, DOB, gender
2. **Addresses**
   - Home, work, other
   - Default address selection
   - Pin on map for accuracy
3. **Payment Methods**
   - Saved cards
   - UPI IDs
   - Wallets
4. **Preferences**
   - Favorite stores
   - Dietary restrictions
   - Preferred languages
5. **Order History**
   - Past orders
   - Reorder functionality
   - Track delivery

---

## Checkout Process

### Checkout Flow

**Component**: `/frontend-pwa/src/pages/customer/CheckoutPage.tsx`

**Steps**:

1. **Review Cart**
   - Verify items and quantities
   - Apply coupons/offers
   - View price breakdown

2. **Select Delivery Address**
   - Choose from saved addresses
   - Add new address
   - Verify delivery availability

3. **Choose Delivery Time**
   - Same-day delivery slots
   - Next-day delivery
   - Scheduled delivery (select date/time)

4. **Select Payment Method**
   - Cash on Delivery (COD)
   - UPI (Google Pay, PhonePe, Paytm)
   - Credit/Debit Card
   - Wallets

5. **Place Order**
   - Confirm order details
   - Submit payment
   - Receive order confirmation

### Address Management

**Features**:
- Multiple saved addresses
- Address type labels (Home, Work, Other)
- Default address marking
- Landmark-based location
- GPS coordinates for accuracy

**Validation**:
- Pincode verification
- Delivery radius check
- Store availability confirmation

### Payment Integration

**Supported Methods**:
- **Cash on Delivery** - Available for all orders
- **UPI** - Real-time payment via UPI apps
- **Cards** - Visa, Mastercard, Rupay
- **Wallets** - Paytm, PhonePe, Amazon Pay

**Payment Status Tracking**:
- Pending → Processing → Success/Failed
- Automatic retry on failure
- Refund processing for cancellations

**Component**: `/frontend-pwa/src/components/PaymentStatusCard.tsx`

---

## Guest Checkout Flow

**Added**: February 11, 2026
**Status**: Production-ready

### Overview

Guest customers (non-authenticated users) can browse stores, add products to cart, and complete checkout without creating an account. This is the primary acquisition funnel for new users.

### Complete Guest Journey

```
/nearby-stores → Search by State/City → Select Store
     ↓
/store/{storeId} → Browse Products → Add to Cart (5-10 items)
     ↓
/checkout → Fill Info → Delivery Details → Payment → Place Order
     ↓
/order/{orderId}/track → Order Confirmation & Tracking
```

### Step 1: Store Discovery (`/nearby-stores`)

**Component**: `/frontend-pwa/src/pages/NearbyStoresEnhanced.tsx`

Guest users can search for stores using:
- **GPS-based search** (recommended, requires location permission)
- **Manual address search** with State + City dropdowns

**Manual Search Flow**:
1. Click "Search by Address" tab
2. Select State from dropdown (e.g., "Uttar Pradesh")
3. Type and select City (e.g., "Lucknow")
4. Auto-search triggers after 500ms debounce
5. Geocodes via Nominatim API → calls `GET /api/v1/stores/nearby?city=Lucknow&state=Uttar Pradesh`

### Step 2: Add Products to Cart (`/store/{storeId}`)

**Component**: `/frontend-pwa/src/pages/StoreDetailPage.tsx`

**Cart Architecture** (Updated Feb 2026):
- Local React state for UI responsiveness (instant +/- buttons)
- **Zustand store** (`useCartStore`) for cross-page persistence
- Both stores are synchronized on every add/remove action
- Cart persisted in `localStorage` under key `vyaparai-cart`

**Floating Cart Bar**:
- Appears at bottom when items > 0
- Shows item count and running total
- "Checkout" button navigates to `/checkout`
- Centered design (max 600px width)

### Step 3: Checkout (`/checkout`)

**Component**: `/frontend-pwa/src/pages/CustomerCheckout.tsx`

Three-step form wizard:

#### Step 3a: Customer Information
| Field | Required | Validation |
|-------|----------|------------|
| Full Name | Yes | Min 2 characters |
| Phone Number | Yes | 10-digit Indian number |
| Email | No | Valid email format |

#### Step 3b: Delivery Details
| Field | Required | Validation |
|-------|----------|------------|
| Delivery Address | Yes | Min 5 characters |
| Landmark | No | Free text |
| City | Yes | Min 2 characters |
| State | Yes | Min 2 characters |
| Pincode | Yes | 6-digit number |
| Delivery Slot | Yes | Select (Morning/Afternoon/Evening) |

#### Step 3c: Payment & Review
- Order summary with all items, subtotal, GST (5%), and total
- Payment method selection (Cash on Delivery)
- "Place Order" button

### Step 4: Order Placement

**Backend API**: `POST /api/v1/orders/`

**Request Payload** (snake_case):
```json
{
  "store_id": "STORE-01KFSG8S99QMDCC0SKK47Q01JB",
  "customer_name": "Raj Kumar",
  "customer_phone": "9876543210",
  "customer_email": "raj@example.com",
  "delivery_address": "123 Main Street, Near Hazratganj, Lucknow, Uttar Pradesh 226001",
  "items": [
    {
      "product_id": "PROD-ABC123",
      "product_name": "Amul Milk 500ml",
      "quantity": 2,
      "unit_price": 30.0,
      "unit": "pieces"
    }
  ],
  "payment_method": "cod",
  "channel": "web"
}
```

**Backend Processing** (Saga Pattern):
1. Validate request → Calculate subtotal
2. Calculate GST (via `gst_service` or 18% fallback)
3. Reserve stock (decrement inventory atomically)
4. Create order record in DynamoDB
5. If any step fails → rollback stock reservations

**Success Response**: Redirects to `/order/{orderId}/track`

### Technical Architecture

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  StoreDetailPage │      │  useCartStore     │      │ CustomerCheckout │
│  (local state +  │─────▶│  (Zustand +       │─────▶│  (reads from     │
│   Zustand sync)  │      │   localStorage)   │      │   Zustand store) │
└──────────────────┘      └──────────────────┘      └────────┬─────────┘
                                                              │
                                                   POST /api/v1/orders/
                                                              │
                                                              ▼
                                                   ┌──────────────────┐
                                                   │  orders.py       │
                                                   │  (validate +     │
                                                   │   GST calc)      │
                                                   └────────┬─────────┘
                                                            │
                                                            ▼
                                                   ┌──────────────────┐
                                                   │  order_txn_svc   │
                                                   │  (saga pattern:  │
                                                   │   reserve stock  │
                                                   │   → create order │
                                                   │   → rollback)    │
                                                   └──────────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `frontend-pwa/src/pages/StoreDetailPage.tsx` | Store page with cart integration |
| `frontend-pwa/src/pages/CustomerCheckout.tsx` | 3-step checkout wizard |
| `frontend-pwa/src/stores/cartStore.ts` | Zustand cart state (localStorage persistence) |
| `backend/app/api/v1/orders.py` | Order creation API endpoint |
| `backend/app/services/order_transaction_service.py` | Saga pattern for stock reservation |
| `backend/app/services/gst_service.py` | GST calculation service |
| `backend/app/services/inventory_service.py` | Stock management and validation |

---

## November 2025 UX Enhancements

### 1. Profile Completion (Optional)

**Change**: Profile fields are now **optional** instead of required

**Impact**:
- Faster onboarding
- Reduced friction
- Higher conversion rates
- Progressive disclosure of benefits

**Implementation**:
- Registration requires only: phone, first name, last name
- Email made optional
- Profile completion encouraged via dashboard prompts

### 2. Cart TTL (30-Day Expiration)

**Feature**: Shopping carts now expire after 30 days

**Benefits**:
- Prevents stale data
- Encourages purchase completion
- Reduces backend storage

**User Experience**:
- Visual countdown timer
- Warning notifications (7 days, 1 day before expiration)
- "Renew Cart" button to extend TTL

### 3. Dual Store Search

**Enhancement**: Added manual search fallback

**Methods**:
1. **GPS Location** (primary)
   - Automatic nearby stores
   - Distance-based sorting

2. **City/State Dropdowns** (fallback)
   - Browse by location
   - Hierarchical selection

3. **Pincode Search** (direct)
   - Enter 6-digit pincode
   - Instant store results

4. **Landmark Search** (contextual)
   - Famous locations
   - Local knowledge utilization

**Component**: `/frontend-pwa/src/components/customer/StoreSearch.tsx`

### 4. Market Prices Integration (data.gov.in)

**Feature**: Live market prices for agricultural products

**Data Source**: Government of India Open Data Portal

**Use Cases**:
- Compare store prices with market rates
- Transparency for customers
- Fair pricing indicators

**Display**:
```
Product: Tomatoes (1 kg)
Store Price: ₹40
Market Price: ₹35-45 (updated today)
[Fair Price Badge]
```

**API Integration**: `GET /api/v1/market-prices/{product}?location={pincode}`

### 5. Enhanced Store Profiles

**Trust-Building Elements**:
- Store history timeline
- Owner stories and background
- Photo and video galleries
- Social impact metrics
- Certifications and licenses
- Community programs
- Customer testimonials

**Component**: `/frontend-pwa/src/pages/customer/EnhancedStoreHomePage.tsx`

---

## Best Practices

### For Customers

1. **Enable Location Permissions**
   - For accurate store discovery
   - Faster delivery time estimates

2. **Complete Your Profile**
   - Faster checkout process
   - Personalized recommendations
   - Order tracking via email

3. **Add Multiple Addresses**
   - Home, work, frequent locations
   - Set default for quick orders

4. **Save Payment Methods**
   - Faster checkout
   - Recurring orders simplified

### For Developers

1. **Progressive Enhancement**
   - Core features work without JavaScript
   - Enhanced features layered on top

2. **Offline Support**
   - Service Worker for offline browsing
   - Cart persists offline
   - Queue orders for later submission

3. **Performance**
   - Lazy load images
   - Code splitting by route
   - Optimize bundle size

4. **Accessibility**
   - WCAG 2.1 AA compliance
   - Keyboard navigation
   - Screen reader support
   - High contrast mode

---

## Troubleshooting

### Common Issues

**1. OTP Not Received**
- Check phone number format (+91XXXXXXXXXX)
- Verify SMS permissions
- Wait 60 seconds before retry
- Check spam/promotions folder

**2. Location Not Working**
- Grant location permissions
- Enable device GPS
- Use manual search fallback
- Try refreshing page

**3. Cart Items Disappeared**
- Check if 30 days passed (TTL expired)
- Verify authentication status
- Check browser storage settings
- Try guest to authenticated migration

**4. Checkout Fails**
- Verify delivery address in range
- Check product availability
- Ensure valid payment method
- Check network connectivity

---

## Future Enhancements

1. **Voice Search** - Search products by voice
2. **AR Product Preview** - View products in your space
3. **Recipe Suggestions** - Based on cart items
4. **Nutrition Tracking** - Health-conscious shopping
5. **Social Shopping** - Share carts with family
6. **Smart Reorder** - AI-powered recurring orders
7. **Price Alerts** - Notify when prices drop
8. **Loyalty Program** - Points and rewards

---

## Related Documentation

- [API Reference](/docs/API_REFERENCE_COMPLETE.md)
- [Database Schema](/backend/database/DATABASE_SCHEMA_DOCUMENTATION.md)
- [Troubleshooting Guide](/docs/TROUBLESHOOTING.md)
- [Master Documentation](/docs/MASTER_DOCUMENTATION.md)

---

**Last Updated**: February 11, 2026
**Document Version**: 1.1.0
**Status**: Production Features Documented
