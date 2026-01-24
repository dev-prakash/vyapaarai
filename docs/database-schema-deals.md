# Store Deals System - Database Architecture

## Overview
This document defines the database schema for the store deals and promotions system in VyapaarAI.

---

## 1. DynamoDB Tables

### Table 1: `store_deals`
**Purpose**: Store all promotional deals created by store owners

**Primary Key**:
- Partition Key: `deal_id` (String) - Format: `DEAL-{ULID}`
- Sort Key: `store_id` (String) - Format: `STORE-{ULID}`

**GSI-1**: `store_id` (PK) + `status#start_date` (SK)
- Query all active/scheduled deals for a store
- Sort by start date

**GSI-2**: `category` (PK) + `discount_percentage` (SK)
- Find deals by category across stores
- Sort by discount value

**GSI-3**: `city#state` (PK) + `end_date` (SK)
- Find active deals in a geographic area
- Sort by expiry date

**Attributes**:
```javascript
{
  deal_id: "DEAL-01K5SBCNYJP5V4ZCP3EVYKH4KV",
  store_id: "STORE-01K5SBCNYJP5V4ZCP3EVYKH4KV",
  store_name: "Green Valley Grocery",

  // Deal Information
  title: "Fresh Vegetables Sale",
  description: "Get 20% off on all fresh vegetables",
  deal_type: "PERCENTAGE_OFF" | "FLAT_DISCOUNT" | "BUY_X_GET_Y" | "CASHBACK" | "FREE_SHIPPING",

  // Discount Details
  discount_value: 20,                    // Percentage or flat amount
  discount_unit: "PERCENT" | "RUPEES",
  min_purchase_amount: 500,              // Minimum cart value
  max_discount_amount: 200,              // Cap on discount

  // Buy X Get Y specifics (if applicable)
  buy_quantity: 2,                       // Buy 2
  get_quantity: 1,                       // Get 1 free

  // Applicable Products
  applicable_to: "ALL" | "CATEGORY" | "PRODUCTS" | "BRANDS",
  category_ids: ["CAT-001", "CAT-002"], // If applicable_to = CATEGORY
  product_ids: ["PROD-001", "PROD-002"], // If applicable_to = PRODUCTS
  brand_names: ["Amul", "Mother Dairy"], // If applicable_to = BRANDS

  // Eligibility Rules
  eligibility_rules: {
    min_order_value: 500,
    max_order_value: 5000,
    first_order_only: false,
    min_items_count: 3,
    user_tier: ["SILVER", "GOLD", "PLATINUM"] | null,
    usage_limit_per_user: 1,
    exclude_sale_items: true
  },

  // Date & Time
  start_date: "2025-12-02T00:00:00Z",
  end_date: "2025-12-15T23:59:59Z",
  timezone: "Asia/Kolkata",
  active_days: ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"],
  active_hours: {
    start: "09:00",
    end: "21:00"
  },

  // Status & Metrics
  status: "DRAFT" | "SCHEDULED" | "ACTIVE" | "PAUSED" | "EXPIRED" | "CANCELLED",
  total_usage_limit: 100,               // Max redemptions
  current_usage_count: 45,              // Times redeemed
  total_revenue_generated: 25000,       // Revenue from this deal
  total_discount_given: 5000,           // Total discount given

  // Marketing
  banner_image_url: "https://s3.../deal-banner.jpg",
  terms_and_conditions: "Valid for online orders only...",
  promo_code: "VEGGIES20" | null,       // Optional promo code

  // Metadata
  city: "Bangalore",
  state: "Karnataka",
  created_at: "2025-12-01T10:30:00Z",
  updated_at: "2025-12-01T10:30:00Z",
  created_by: "admin@store.com"
}
```

---

### Table 2: `deal_redemptions`
**Purpose**: Track individual deal redemptions by customers

**Primary Key**:
- Partition Key: `redemption_id` (String) - Format: `REDEEM-{ULID}`
- Sort Key: `customer_id#deal_id` (String)

**GSI-1**: `deal_id` (PK) + `redeemed_at` (SK)
- Query all redemptions for a deal
- Sort by redemption time

**GSI-2**: `customer_id` (PK) + `redeemed_at` (SK)
- Query customer's deal usage history

**Attributes**:
```javascript
{
  redemption_id: "REDEEM-01K5SBCNYJP5V4ZCP3EVYKH4KV",
  customer_id: "CUST-01K5SBCNYJP5V4ZCP3EVYKH4KV",
  deal_id: "DEAL-01K5SBCNYJP5V4ZCP3EVYKH4KV",
  store_id: "STORE-01K5SBCNYJP5V4ZCP3EVYKH4KV",
  order_id: "ORDER-01K5SBCNYJP5V4ZCP3EVYKH4KV",

  // Redemption Details
  original_amount: 1000,
  discount_applied: 200,
  final_amount: 800,
  promo_code_used: "VEGGIES20" | null,

  // Metadata
  redeemed_at: "2025-12-02T15:30:00Z",
  status: "APPLIED" | "REFUNDED"
}
```

---

### Table 3: `deal_analytics`
**Purpose**: Daily aggregated analytics for deals

**Primary Key**:
- Partition Key: `deal_id#date` (String) - Format: `DEAL-{ULID}#2025-12-02`
- Sort Key: `metric_type` (String) - "VIEWS" | "CLICKS" | "REDEMPTIONS" | "REVENUE"

**Attributes**:
```javascript
{
  deal_id: "DEAL-01K5SBCNYJP5V4ZCP3EVYKH4KV",
  date: "2025-12-02",
  metric_type: "REDEMPTIONS",

  // Metrics
  count: 45,
  total_revenue: 25000,
  total_discount: 5000,
  unique_customers: 40,

  // Hourly breakdown
  hourly_data: {
    "09": 5,
    "10": 8,
    "11": 12,
    // ... etc
  }
}
```

---

## 2. Deal Types & Business Rules

### Deal Type 1: PERCENTAGE_OFF
**Example**: 20% off on Fresh Vegetables

```javascript
{
  deal_type: "PERCENTAGE_OFF",
  discount_value: 20,
  discount_unit: "PERCENT",
  max_discount_amount: 200,
  applicable_to: "CATEGORY",
  category_ids: ["CAT-VEGETABLES"]
}
```

**Calculation**:
```
discount = min(cart_value * 0.20, max_discount_amount)
final_amount = cart_value - discount
```

---

### Deal Type 2: FLAT_DISCOUNT
**Example**: Flat ₹100 off on orders above ₹500

```javascript
{
  deal_type: "FLAT_DISCOUNT",
  discount_value: 100,
  discount_unit: "RUPEES",
  min_purchase_amount: 500
}
```

**Calculation**:
```
if (cart_value >= min_purchase_amount) {
  discount = discount_value
  final_amount = cart_value - discount
}
```

---

### Deal Type 3: BUY_X_GET_Y
**Example**: Buy 2 Get 1 Free on Dairy Products

```javascript
{
  deal_type: "BUY_X_GET_Y",
  buy_quantity: 2,
  get_quantity: 1,
  applicable_to: "CATEGORY",
  category_ids: ["CAT-DAIRY"]
}
```

**Calculation**:
```
eligible_items = items.filter(item => category_ids.includes(item.category))
sets = floor(eligible_items.length / (buy_quantity + get_quantity))
free_items = sets * get_quantity
discount = sum(cheapest_items_in_each_set.price)
```

---

### Deal Type 4: CASHBACK
**Example**: Get ₹50 cashback on orders above ₹1000

```javascript
{
  deal_type: "CASHBACK",
  discount_value: 50,
  discount_unit: "RUPEES",
  min_purchase_amount: 1000
}
```

**Note**: Cashback is credited to customer wallet after order completion.

---

### Deal Type 5: FREE_SHIPPING
**Example**: Free shipping on orders above ₹300

```javascript
{
  deal_type: "FREE_SHIPPING",
  min_purchase_amount: 300
}
```

---

## 3. Eligibility Rules Structure

### Rule 1: Order Value Range
```javascript
{
  min_order_value: 500,
  max_order_value: 5000  // null = no max
}
```

### Rule 2: First Order Only
```javascript
{
  first_order_only: true  // Only for new customers
}
```

### Rule 3: Usage Limits
```javascript
{
  usage_limit_per_user: 1,      // Each customer can use once
  total_usage_limit: 100        // Deal expires after 100 uses
}
```

### Rule 4: Customer Tier
```javascript
{
  user_tier: ["GOLD", "PLATINUM"]  // Only for premium customers
}
```

### Rule 5: Item Count
```javascript
{
  min_items_count: 3  // Cart must have at least 3 items
}
```

### Rule 6: Time Restrictions
```javascript
{
  active_days: ["SAT", "SUN"],  // Weekend only
  active_hours: {
    start: "18:00",
    end: "21:00"              // Evening rush hour
  }
}
```

---

## 4. Deal Status Lifecycle

```
DRAFT → User is creating deal, not visible to customers
  ↓
SCHEDULED → Deal created, waiting for start_date
  ↓
ACTIVE → Currently running and visible to customers
  ↓
PAUSED → Temporarily disabled by store owner
  ↓
EXPIRED → end_date reached, no longer active
  ↓
CANCELLED → Manually cancelled by store owner
```

---

## 5. API Endpoints

### Store Owner Endpoints

**Create Deal**
```
POST /api/v1/stores/{store_id}/deals
Body: {deal object}
Response: {deal_id, status}
```

**Update Deal**
```
PUT /api/v1/stores/{store_id}/deals/{deal_id}
Body: {updated fields}
Response: {success}
```

**Get Store Deals**
```
GET /api/v1/stores/{store_id}/deals?status=ACTIVE&limit=20
Response: {deals: [...], total: 5}
```

**Deal Analytics**
```
GET /api/v1/stores/{store_id}/deals/{deal_id}/analytics?start_date=2025-12-01&end_date=2025-12-07
Response: {
  views: 500,
  clicks: 200,
  redemptions: 45,
  revenue: 25000,
  roi: 400%
}
```

### Customer Endpoints

**Get Active Deals (All Stores)**
```
GET /api/v1/deals?city=Bangalore&category=VEGETABLES&limit=20
Response: {deals: [...]}
```

**Get Store Specific Deals**
```
GET /api/v1/stores/{store_id}/deals/active
Response: {deals: [...]}
```

**Apply Deal to Cart**
```
POST /api/v1/cart/apply-deal
Body: {
  cart_id: "...",
  deal_id: "...",
  promo_code: "VEGGIES20"
}
Response: {
  original_amount: 1000,
  discount: 200,
  final_amount: 800
}
```

---

## 6. Deal Duration & Expiry

### Automatic Expiry
Deals automatically expire when:
1. `end_date` is reached
2. `total_usage_limit` is exhausted
3. Store owner cancels the deal

### Background Job
Run every hour to:
1. Check deals where `end_date < current_time` and `status = ACTIVE`
2. Update status to `EXPIRED`
3. Send notification to store owner with final analytics

### Deal Renewal
Store owners can:
1. Clone expired deal with new dates
2. Extend end_date of active deal
3. Increase total_usage_limit

---

## 7. Best Practices

### For Store Owners
1. **Start Small**: Begin with 10-20% discounts to test customer response
2. **Time-bound**: 7-14 day deals work best (creates urgency)
3. **Clear Terms**: Always specify min order value and exclusions
4. **Monitor Daily**: Check analytics to pause underperforming deals
5. **Stock Planning**: Ensure adequate stock for deal items

### For Platform
1. **Approval Process**: Review deals before ACTIVE status (optional)
2. **Fraud Detection**: Monitor for abuse (same user, multiple accounts)
3. **Performance**: Cache active deals by location
4. **Notifications**: Alert customers about expiring deals (24hrs before)

---

## 8. Example Scenarios

### Scenario 1: Weekend Sale
```javascript
{
  title: "Weekend Special - 15% Off Everything",
  deal_type: "PERCENTAGE_OFF",
  discount_value: 15,
  applicable_to: "ALL",
  active_days: ["SAT", "SUN"],
  min_purchase_amount: 300,
  start_date: "2025-12-07T00:00:00Z",
  end_date: "2025-12-08T23:59:59Z"
}
```

### Scenario 2: New Customer Welcome
```javascript
{
  title: "New Customer - Flat ₹100 Off",
  deal_type: "FLAT_DISCOUNT",
  discount_value: 100,
  eligibility_rules: {
    first_order_only: true,
    min_order_value: 500
  },
  total_usage_limit: 100
}
```

### Scenario 3: Category Promotion
```javascript
{
  title: "Dairy Products - Buy 2 Get 1 Free",
  deal_type: "BUY_X_GET_Y",
  buy_quantity: 2,
  get_quantity: 1,
  applicable_to: "CATEGORY",
  category_ids: ["CAT-DAIRY"],
  start_date: "2025-12-01T00:00:00Z",
  end_date: "2025-12-31T23:59:59Z"
}
```

---

## 9. Implementation Priority

### Phase 1 (MVP)
- [x] Database schema design
- [ ] PERCENTAGE_OFF deal type
- [ ] FLAT_DISCOUNT deal type
- [ ] Basic eligibility rules (min_order_value, usage_limit)
- [ ] Store owner: Create/Edit/View deals
- [ ] Customer: View active deals
- [ ] Apply deal to cart

### Phase 2
- [ ] BUY_X_GET_Y deal type
- [ ] CASHBACK deal type
- [ ] Advanced eligibility (first_order, customer_tier)
- [ ] Deal analytics dashboard
- [ ] Promo codes
- [ ] Deal expiry notifications

### Phase 3
- [ ] Time-based deals (active_hours, active_days)
- [ ] Geographic targeting
- [ ] A/B testing for deals
- [ ] Fraud detection
- [ ] Deal recommendation engine

---

## 10. Estimated Costs (AWS DynamoDB)

### Storage
- ~5KB per deal
- 1000 stores × 5 deals = 5000 deals
- 5000 × 5KB = 25MB
- **Cost**: ~$0.01/month

### Read/Write Operations
- 100K deal views/day = 100K reads
- 10K deal applications/day = 10K writes
- **Cost**: ~$30-40/month

### GSI
- 3 GSIs × 25MB = 75MB additional storage
- **Cost**: ~$0.03/month

**Total Monthly**: ~$40-50 for medium-scale deployment
