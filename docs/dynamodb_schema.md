# VyaparAI DynamoDB Schema Documentation

## Overview

This document provides comprehensive schema documentation for all DynamoDB tables used in the VyaparAI platform. The platform uses a hybrid database architecture with DynamoDB for hot-path operations and PostgreSQL for analytics.

### Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      VyaparAI DynamoDB Architecture                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    CORE OPERATIONAL TABLES                       │   │
│  │                                                                   │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │   │
│  │  │ OrdersTable  │ │ SessionsTable│ │  StoresTable │              │   │
│  │  │ (Hot-path)   │ │ (Session)    │ │ (Master data)│              │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘              │   │
│  │                                                                   │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │   │
│  │  │ProductsTable │ │ MetricsTable │ │RateLimitsTable│             │   │
│  │  │ (Catalog)    │ │ (Analytics)  │ │ (Rate limit) │              │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    KHATA (CREDIT) TABLES                         │   │
│  │                                                                   │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │   │
│  │  │ Transactions │ │  Balances    │ │  Reminders   │              │   │
│  │  │ (Ledger)     │ │ (Cache)      │ │ (Scheduled)  │              │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘              │   │
│  │                                                                   │   │
│  │  ┌──────────────┐                                                │   │
│  │  │ Idempotency  │                                                │   │
│  │  │ (Dedup)      │                                                │   │
│  │  └──────────────┘                                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Table Naming Convention

All tables follow the pattern: `vyaparai-{table-name}-{stage}`

- **dev**: Development environment
- **staging**: Staging environment
- **prod**: Production environment

---

## Core Operational Tables

### 1. OrdersTable

**Table Name**: `vyaparai-orders-{stage}`

**Purpose**: Stores all order information for hot-path operations (order creation, status updates, real-time queries)

**Features**:
- DynamoDB Streams enabled (NEW_AND_OLD_IMAGES)
- TTL enabled for automatic data expiration
- Point-in-Time Recovery enabled
- Server-Side Encryption enabled

#### Key Schema

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `pk` | String | HASH (Partition Key) | Composite key pattern |
| `sk` | String | RANGE (Sort Key) | Composite key pattern |

**Note**: In practice, the table uses `store_id` as HASH and `id` as RANGE for order storage.

#### Actual Storage Pattern

```json
{
  "store_id": "STR-K3FJ82",           // HASH key (partition key)
  "id": "ORD-20240115-AB12CD34",      // RANGE key (sort key)
  "customer_id": "CUST-A1B2C3D4",
  "customer_phone": "+919876543210",
  "customer_name": "Ramesh Kumar",
  "items": [
    {
      "product_id": "PROD-123",
      "name": "Tata Salt 1kg",
      "quantity": 2,
      "price": 25.00,
      "unit": "kg"
    }
  ],
  "total_amount": 50.00,
  "status": "confirmed",
  "channel": "whatsapp",
  "language": "hi",
  "intent": "order_create",
  "confidence": 0.95,
  "entities": [
    {"type": "product", "value": "salt", "confidence": 0.92}
  ],
  "payment_method": "cod",
  "delivery_address": "123 Main St, Delhi",
  "delivery_notes": "Call before delivery",
  "order_number": "ORD-20240115-AB12CD34",
  "tracking_id": "TRK-XYZ789",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z",
  "ttl": 1710288000
}
```

#### Global Secondary Indexes

| Index Name | Partition Key | Sort Key | Projection | Purpose |
|------------|---------------|----------|------------|---------|
| GSI1 | `gsi1pk` | `gsi1sk` | ALL | Query by customer phone |
| GSI2 | `gsi2pk` | `gsi2sk` | ALL | Query by date range |
| GSI3 | `gsi3pk` | `gsi3sk` | ALL | Query by status |
| order-id-index | `id` | - | ALL | Direct order lookup |
| store_id-created_at-index | `store_id` | `created_at` | ALL | Store order history |

#### Access Patterns

| Access Pattern | Key Condition | Index |
|----------------|---------------|-------|
| Get order by ID | `id = :order_id` | order-id-index |
| Get store orders by date | `store_id = :store_id AND created_at BETWEEN :start AND :end` | store_id-created_at-index |
| Get customer order history | `gsi1pk = CUSTOMER#{phone}` | GSI1 |

---

### 2. SessionsTable

**Table Name**: `vyaparai-sessions-{stage}`

**Purpose**: Stores user session data for real-time conversation context

**Features**:
- TTL enabled (sessions auto-expire)
- Point-in-Time Recovery enabled
- Server-Side Encryption enabled

#### Key Schema

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `pk` | String | HASH | Session identifier: `SESSION#{session_id}` |

#### Sample Data Structure

```json
{
  "pk": "SESSION#sess-abc123def456",
  "session_id": "sess-abc123def456",
  "customer_phone": "+919876543210",
  "store_id": "STR-K3FJ82",
  "context": {
    "current_order": null,
    "conversation_history": [
      {"role": "user", "message": "2 kg rice chahiye", "timestamp": "2024-01-15T10:30:00Z"},
      {"role": "assistant", "message": "Kaun sa rice? Basmati ya regular?", "timestamp": "2024-01-15T10:30:05Z"}
    ],
    "selected_products": [],
    "pending_confirmation": false
  },
  "last_activity": "2024-01-15T10:30:05Z",
  "gsi1pk": "CUSTOMER#+919876543210",
  "gsi1sk": "2024-01-15T10:30:05Z",
  "ttl": 1705320600
}
```

#### Global Secondary Indexes

| Index Name | Partition Key | Sort Key | Projection | Purpose |
|------------|---------------|----------|------------|---------|
| GSI1 | `gsi1pk` | `gsi1sk` | ALL | Query sessions by customer phone |

#### Access Patterns

| Access Pattern | Key Condition | Index |
|----------------|---------------|-------|
| Get session by ID | `pk = SESSION#{session_id}` | Primary |
| Get customer sessions | `gsi1pk = CUSTOMER#{phone}` | GSI1 |

---

### 3. StoresTable

**Table Name**: `vyaparai-stores-{stage}`

**Purpose**: Master data storage for store information

**Features**:
- Point-in-Time Recovery enabled
- Server-Side Encryption enabled
- No TTL (permanent data)

#### Key Schema

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `pk` | String | HASH | Store identifier (same as `id`) |

#### Sample Data Structure

```json
{
  "pk": "STR-K3FJ82",
  "id": "STR-K3FJ82",
  "store_id": "STR-K3FJ82",
  "name": "Sharma Kirana Store",
  "owner_id": "OWNER-A1B2C3D4",
  "owner_name": "Rajesh Sharma",
  "address": {
    "street": "123 MG Road",
    "city": "Delhi",
    "state": "Delhi",
    "pincode": "110001",
    "landmark": "Near Metro Station"
  },
  "latitude": 28.6139,
  "longitude": 77.2090,
  "contact_info": {
    "phone": "+919876543210",
    "whatsapp": "+919876543210",
    "email": "sharma.kirana@gmail.com"
  },
  "settings": {
    "accepts_online_payment": true,
    "delivery_radius_km": 5,
    "min_order_amount": 100,
    "business_hours": {
      "monday": {"open": "08:00", "close": "21:00"},
      "sunday": {"open": "10:00", "close": "14:00"}
    }
  },
  "status": "active",
  "verified": true,
  "gstin": "07AABCU9603R1ZM",
  "store_type": "grocery",
  "gsi1pk": "OWNER#OWNER-A1B2C3D4",
  "gsi1sk": "2024-01-15T10:00:00Z",
  "gsi2pk": "CITY#Delhi",
  "gsi2sk": "STR-K3FJ82",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T12:00:00Z"
}
```

#### Global Secondary Indexes

| Index Name | Partition Key | Sort Key | Projection | Purpose |
|------------|---------------|----------|------------|---------|
| GSI1 | `gsi1pk` | `gsi1sk` | ALL | Query stores by owner |
| GSI2 | `gsi2pk` | `gsi2sk` | ALL | Query stores by city/location |

#### Access Patterns

| Access Pattern | Key Condition | Index |
|----------------|---------------|-------|
| Get store by ID | `pk = :store_id` | Primary |
| Get owner's stores | `gsi1pk = OWNER#{owner_id}` | GSI1 |
| Get stores by city | `gsi2pk = CITY#{city}` | GSI2 |

---

### 4. ProductsTable

**Table Name**: `vyaparai-products-{stage}`

**Purpose**: Product catalog storage per store

**Features**:
- Point-in-Time Recovery enabled
- Server-Side Encryption enabled
- No TTL (permanent catalog data)

#### Key Schema

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `pk` | String | HASH | Store identifier: `STORE#{store_id}` |
| `sk` | String | RANGE | Product identifier: `PRODUCT#{product_id}` |

#### Sample Data Structure

```json
{
  "pk": "STORE#STR-K3FJ82",
  "sk": "PRODUCT#PROD-ABC123",
  "product_id": "PROD-ABC123",
  "store_id": "STR-K3FJ82",
  "name": "Tata Salt",
  "local_name": "टाटा नमक",
  "category": "grocery",
  "subcategory": "spices",
  "brand": "Tata",
  "variants": [
    {"size": "1kg", "price": 25.00, "sku": "TATA-SALT-1KG"},
    {"size": "500g", "price": 15.00, "sku": "TATA-SALT-500G"}
  ],
  "unit": "kg",
  "price": 25.00,
  "mrp": 28.00,
  "stock_quantity": 50,
  "low_stock_threshold": 10,
  "image_url": "https://cdn.vyaparai.com/products/tata-salt.jpg",
  "keywords": ["salt", "namak", "iodized", "table salt"],
  "metadata": {
    "weight": "1kg",
    "barcode": "8901030000072"
  },
  "gsi1pk": "CATEGORY#grocery",
  "gsi1sk": "BRAND#Tata#PROD-ABC123",
  "gsi2pk": "BRAND#Tata",
  "gsi2sk": "STORE#STR-K3FJ82#PROD-ABC123",
  "gsi3pk": "STORE#STR-K3FJ82",
  "gsi3sk": "CATEGORY#grocery#Tata Salt",
  "is_active": true,
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T12:00:00Z"
}
```

#### Global Secondary Indexes

| Index Name | Partition Key | Sort Key | Projection | Purpose |
|------------|---------------|----------|------------|---------|
| GSI1 | `gsi1pk` | `gsi1sk` | ALL | Query by category |
| GSI2 | `gsi2pk` | `gsi2sk` | ALL | Query by brand |
| GSI3 | `gsi3pk` | `gsi3sk` | ALL | Store product listing |

#### Access Patterns

| Access Pattern | Key Condition | Index |
|----------------|---------------|-------|
| Get store products | `pk = STORE#{store_id}` | Primary |
| Get single product | `pk = STORE#{store_id} AND sk = PRODUCT#{product_id}` | Primary |
| Get products by category | `gsi1pk = CATEGORY#{category}` | GSI1 |
| Get products by brand | `gsi2pk = BRAND#{brand}` | GSI2 |
| Search store catalog | `gsi3pk = STORE#{store_id}` | GSI3 |

---

### 5. MetricsTable

**Table Name**: `vyaparai-metrics-{stage}`

**Purpose**: Stores aggregated metrics and analytics data

**Features**:
- TTL enabled (metrics auto-expire after retention period)
- Point-in-Time Recovery enabled
- Server-Side Encryption enabled

#### Key Schema

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `pk` | String | HASH | Metric scope: `STORE#{store_id}` or `SYSTEM` |
| `sk` | String | RANGE | Metric type and timestamp: `METRIC#{type}#{date}` |

#### Sample Data Structure

```json
{
  "pk": "STORE#STR-K3FJ82",
  "sk": "METRIC#daily_orders#2024-01-15",
  "metric_type": "daily_orders",
  "date": "2024-01-15",
  "store_id": "STR-K3FJ82",
  "values": {
    "total_orders": 45,
    "confirmed_orders": 40,
    "cancelled_orders": 5,
    "total_revenue": 12500.00,
    "average_order_value": 277.78,
    "unique_customers": 30
  },
  "channel_breakdown": {
    "whatsapp": 25,
    "sms": 10,
    "web": 8,
    "rcs": 2
  },
  "gsi1pk": "DATE#2024-01-15",
  "gsi1sk": "STORE#STR-K3FJ82",
  "ttl": 1718064000,
  "created_at": "2024-01-16T00:00:00Z"
}
```

#### Global Secondary Indexes

| Index Name | Partition Key | Sort Key | Projection | Purpose |
|------------|---------------|----------|------------|---------|
| GSI1 | `gsi1pk` | `gsi1sk` | ALL | Query metrics by date across stores |

#### Access Patterns

| Access Pattern | Key Condition | Index |
|----------------|---------------|-------|
| Get store metrics | `pk = STORE#{store_id} AND sk BEGINS_WITH METRIC#` | Primary |
| Get daily metrics | `pk = STORE#{store_id} AND sk = METRIC#daily_orders#{date}` | Primary |
| Get all stores' metrics for date | `gsi1pk = DATE#{date}` | GSI1 |

---

### 6. RateLimitsTable

**Table Name**: `vyaparai-rate-limits-{stage}`

**Purpose**: Stores rate limiting counters and quotas

**Features**:
- TTL enabled (counters auto-reset)
- Point-in-Time Recovery enabled
- Server-Side Encryption enabled

#### Key Schema

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `pk` | String | HASH | Rate limit key: `RATE_LIMIT#{identifier}` |
| `sk` | String | RANGE | Limit type and window: `{type}#{window}` |

#### Sample Data Structure

```json
{
  "pk": "RATE_LIMIT#+919876543210",
  "sk": "api_calls#minute",
  "identifier": "+919876543210",
  "limit_type": "api_calls",
  "window": "minute",
  "count": 15,
  "limit": 60,
  "window_start": "2024-01-15T10:30:00Z",
  "gsi1pk": "LIMIT_TYPE#api_calls",
  "gsi1sk": "2024-01-15T10:30:00Z#+919876543210",
  "ttl": 1705320660,
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### Global Secondary Indexes

| Index Name | Partition Key | Sort Key | Projection | Purpose |
|------------|---------------|----------|------------|---------|
| GSI1 | `gsi1pk` | `gsi1sk` | ALL | Query rate limits by type |

#### Access Patterns

| Access Pattern | Key Condition | Index |
|----------------|---------------|-------|
| Get rate limit | `pk = RATE_LIMIT#{identifier} AND sk = {type}#{window}` | Primary |
| Get limits by type | `gsi1pk = LIMIT_TYPE#{type}` | GSI1 |

---

## Khata (Credit Management) Tables

### 7. KhataTransactionsTable

**Table Name**: `vyaparai-khata-transactions-{stage}`

**Purpose**: Immutable ledger of all credit sales and payment transactions

**Features**:
- Idempotency key support for deduplication
- Append-only design for audit trail
- No TTL (permanent ledger)

#### Key Schema

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `pk` | String | HASH | Transaction ID: `TXN#{transaction_id}` |
| `sk` | String | RANGE | Store and customer: `STORE#{store_id}#CUST#{phone}` |

#### Sample Data Structure

```json
{
  "pk": "TXN#txn-20240115-abc123",
  "sk": "STORE#STR-K3FJ82#CUST#+919876543210",
  "transaction_id": "txn-20240115-abc123",
  "store_id": "STR-K3FJ82",
  "customer_phone": "+919876543210",
  "transaction_type": "credit_sale",
  "amount": 500.00,
  "balance_before": 1000.00,
  "balance_after": 1500.00,
  "order_id": "ORD-20240115-XYZ789",
  "items": [
    {"name": "Tata Salt 1kg", "quantity": 2, "price": 25.00},
    {"name": "Amul Butter 500g", "quantity": 1, "price": 250.00}
  ],
  "notes": "Monthly grocery purchase",
  "reference_id": "REC-2024-001",
  "idempotency_key": "idem-key-abc123",
  "created_by": "OWNER-A1B2C3D4",
  "gsi1pk": "PHONE#+919876543210",
  "gsi1sk": "STORE#STR-K3FJ82#2024-01-15T10:30:00Z",
  "gsi2pk": "STORE#STR-K3FJ82",
  "gsi2sk": "DATE#2024-01-15#txn-20240115-abc123",
  "metadata": {
    "source": "pos",
    "device_id": "POS-001"
  },
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### Transaction Types

| Type | Description |
|------|-------------|
| `credit_sale` | Customer purchases on credit (increases balance) |
| `payment` | Customer pays off credit (decreases balance) |
| `adjustment` | Manual balance adjustment by store owner |
| `reversal` | Transaction reversal/refund |

#### Global Secondary Indexes

| Index Name | Partition Key | Sort Key | Projection | Purpose |
|------------|---------------|----------|------------|---------|
| GSI1 | `gsi1pk` | `gsi1sk` | ALL | Query by customer phone across stores |
| GSI2 | `gsi2pk` | `gsi2sk` | ALL | Query store transactions by date |

#### Access Patterns

| Access Pattern | Key Condition | Index |
|----------------|---------------|-------|
| Get transaction by ID | `pk = TXN#{transaction_id}` | Primary |
| Get customer transactions | `gsi1pk = PHONE#{phone}` | GSI1 |
| Get store transactions by date | `gsi2pk = STORE#{store_id} AND sk BEGINS_WITH DATE#{date}` | GSI2 |

---

### 8. CustomerBalancesTable

**Table Name**: `vyaparai-customer-balances-{stage}`

**Purpose**: Real-time cache of customer outstanding balances per store

**Features**:
- Optimistic locking with version attribute
- Denormalized for fast reads
- Updated atomically with transactions

#### Key Schema

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `pk` | String | HASH | Store identifier: `STORE#{store_id}` |
| `sk` | String | RANGE | Customer phone: `CUST#{phone}` |

#### Sample Data Structure

```json
{
  "pk": "STORE#STR-K3FJ82",
  "sk": "CUST#+919876543210",
  "store_id": "STR-K3FJ82",
  "customer_phone": "+919876543210",
  "customer_name": "Ramesh Kumar",
  "outstanding_balance": 1500.00,
  "credit_limit": 5000.00,
  "version": 42,
  "last_transaction_id": "txn-20240115-abc123",
  "last_transaction_at": "2024-01-15T10:30:00Z",
  "reminder_enabled": true,
  "reminder_frequency": "weekly",
  "preferred_language": "hi",
  "gsi1pk": "PHONE#+919876543210",
  "gsi1sk": "STORE#STR-K3FJ82",
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

#### Global Secondary Indexes

| Index Name | Partition Key | Sort Key | Projection | Purpose |
|------------|---------------|----------|------------|---------|
| GSI1 | `gsi1pk` | `gsi1sk` | ALL | Query customer balances across all stores |

#### Access Patterns

| Access Pattern | Key Condition | Index |
|----------------|---------------|-------|
| Get customer balance at store | `pk = STORE#{store_id} AND sk = CUST#{phone}` | Primary |
| Get all store customers | `pk = STORE#{store_id}` | Primary |
| Get customer's all store balances | `gsi1pk = PHONE#{phone}` | GSI1 |

---

### 9. PaymentRemindersTable

**Table Name**: `vyaparai-payment-reminders-{stage}`

**Purpose**: Scheduled payment reminders for customers with outstanding balances

**Features**:
- TTL enabled (reminders auto-expire after send)
- Retry tracking for failed sends
- Multi-channel support (SMS, Push, Both)

#### Key Schema

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `pk` | String | HASH | Reminder ID: `REMINDER#{reminder_id}` |
| `sk` | String | RANGE | Scheduled time: `SCHEDULED#{timestamp}` |

#### Sample Data Structure

```json
{
  "pk": "REMINDER#rem-20240120-xyz789",
  "sk": "SCHEDULED#2024-01-20T09:00:00Z",
  "reminder_id": "rem-20240120-xyz789",
  "store_id": "STR-K3FJ82",
  "customer_phone": "+919876543210",
  "outstanding_amount": 1500.00,
  "scheduled_at": "2024-01-20T09:00:00Z",
  "status": "scheduled",
  "reminder_type": "sms",
  "message_template": "payment_reminder_weekly",
  "language": "hi",
  "retry_count": 0,
  "failure_reason": null,
  "gsi1pk": "STORE#STR-K3FJ82",
  "gsi1sk": "STATUS#scheduled#2024-01-20T09:00:00Z",
  "created_at": "2024-01-15T10:30:00Z",
  "sent_at": null,
  "ttl": 1705881600
}
```

#### Reminder Status Values

| Status | Description |
|--------|-------------|
| `scheduled` | Reminder is pending to be sent |
| `sent` | Reminder was successfully sent |
| `failed` | Reminder send failed (check failure_reason) |
| `cancelled` | Reminder was cancelled |

#### Global Secondary Indexes

| Index Name | Partition Key | Sort Key | Projection | Purpose |
|------------|---------------|----------|------------|---------|
| GSI1 | `gsi1pk` | `gsi1sk` | ALL | Query store reminders by status |

---

### 10. IdempotencyKeysTable

**Table Name**: `vyaparai-idempotency-keys-{stage}`

**Purpose**: Prevents duplicate transaction processing using idempotency keys

**Features**:
- TTL enabled (keys expire after 30 days)
- Stores transaction result for replay

#### Key Schema

| Attribute | Type | Key Type | Description |
|-----------|------|----------|-------------|
| `pk` | String | HASH | Idempotency key: `IDEM#{key}` |

#### Sample Data Structure

```json
{
  "pk": "IDEM#client-req-abc123-20240115",
  "idempotency_key": "client-req-abc123-20240115",
  "transaction_id": "txn-20240115-abc123",
  "result": {
    "success": true,
    "transaction_id": "txn-20240115-abc123",
    "new_balance": 1500.00
  },
  "created_at": "2024-01-15T10:30:00Z",
  "ttl": 1707840600
}
```

#### Access Patterns

| Access Pattern | Key Condition | Index |
|----------------|---------------|-------|
| Check idempotency key | `pk = IDEM#{key}` | Primary |

---

## Table Relationships

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Table Relationships                               │
└─────────────────────────────────────────────────────────────────────────┘

StoresTable ─────────┬─────────────────────────────────────────────────────
     │               │
     │ store_id      │ store_id
     ▼               ▼
┌─────────────┐ ┌─────────────┐
│ OrdersTable │ │ProductsTable│
└─────────────┘ └─────────────┘
     │
     │ order_id (optional)
     ▼
┌─────────────────────────┐
│ KhataTransactionsTable  │◄───────┐
└─────────────────────────┘        │
     │                             │ idempotency_key
     │ customer_phone, store_id    │
     ▼                             │
┌─────────────────────────┐ ┌─────────────────────┐
│ CustomerBalancesTable   │ │ IdempotencyKeysTable│
└─────────────────────────┘ └─────────────────────┘
     │
     │ customer_phone, store_id
     ▼
┌─────────────────────────┐
│ PaymentRemindersTable   │
└─────────────────────────┘

SessionsTable ──────────────────────────────────────────────────────────────
     │
     │ store_id (context)
     │ customer_phone
     ▼
Connected to: StoresTable, OrdersTable (for order context)

MetricsTable ───────────────────────────────────────────────────────────────
     │
     │ store_id
     ▼
Aggregated from: OrdersTable (via DynamoDB Streams)

RateLimitsTable ────────────────────────────────────────────────────────────
     │
     │ identifier (phone/IP/API key)
     ▼
Applied to: All API endpoints
```

---

## DynamoDB Streams Configuration

### OrdersTable Stream

**Stream ARN**: `!GetAtt OrdersTable.StreamArn`

**View Type**: `NEW_AND_OLD_IMAGES`

**Purpose**:
- Trigger analytics aggregation
- Sync to PostgreSQL for complex queries
- Send order notifications
- Update inventory

**Stream Processor**: `app.database.stream_processor.process_order_stream`

```python
# Stream event processing
async def process_order_stream(event):
    for record in event['Records']:
        if record['eventName'] == 'INSERT':
            # New order created
            await aggregate_metrics(record['dynamodb']['NewImage'])
            await sync_to_postgresql(record['dynamodb']['NewImage'])
        elif record['eventName'] == 'MODIFY':
            # Order updated
            await handle_status_change(
                record['dynamodb']['OldImage'],
                record['dynamodb']['NewImage']
            )
```

---

## Best Practices Implemented

### 1. Single-Table Design Patterns
- Composite keys (pk/sk) for flexible queries
- GSIs for alternate access patterns
- Sparse indexes for filtered queries

### 2. Optimistic Locking
```python
# CustomerBalances uses version for concurrent updates
table.update_item(
    Key={'pk': store_key, 'sk': customer_key},
    UpdateExpression='SET balance = :new_balance, version = :new_version',
    ConditionExpression='version = :current_version',
    ExpressionAttributeValues={
        ':new_balance': new_balance,
        ':new_version': current_version + 1,
        ':current_version': current_version
    }
)
```

### 3. Idempotency Pattern
- Prevents duplicate transactions
- Stores result for replay
- 30-day TTL for automatic cleanup

### 4. TTL for Data Lifecycle
| Table | TTL Field | Retention |
|-------|-----------|-----------|
| OrdersTable | `ttl` | Configurable |
| SessionsTable | `ttl` | 30 minutes |
| RateLimitsTable | `ttl` | 1-60 minutes |
| MetricsTable | `ttl` | 90 days |
| PaymentRemindersTable | `ttl` | 7 days after scheduled |
| IdempotencyKeysTable | `ttl` | 30 days |

### 5. Cursor-Based Pagination
```python
# Using LastEvaluatedKey for pagination
response = table.query(
    KeyConditionExpression=Key('pk').eq(store_key),
    ExclusiveStartKey=cursor,
    Limit=page_size
)
next_cursor = response.get('LastEvaluatedKey')
```

---

## Capacity Planning

### Billing Mode
All tables use **PAY_PER_REQUEST** (On-Demand) billing for:
- Automatic scaling
- No capacity planning required
- Cost optimization for variable workloads

### Estimated Capacity (Production)

| Table | Read Capacity (avg) | Write Capacity (avg) | Storage |
|-------|---------------------|----------------------|---------|
| OrdersTable | 500-2000 RCU | 100-500 WCU | 10-50 GB |
| SessionsTable | 1000-5000 RCU | 500-2000 WCU | 1-5 GB |
| StoresTable | 100-500 RCU | 10-50 WCU | 1-5 GB |
| ProductsTable | 200-1000 RCU | 50-200 WCU | 5-20 GB |
| MetricsTable | 50-200 RCU | 20-100 WCU | 5-20 GB |
| RateLimitsTable | 1000-5000 RCU | 1000-5000 WCU | <1 GB |
| KhataTransactions | 100-500 RCU | 50-200 WCU | 5-20 GB |
| CustomerBalances | 500-2000 RCU | 100-500 WCU | 1-5 GB |

---

## Security Configuration

### Encryption
- **At Rest**: Server-Side Encryption (SSE) enabled on all tables
- **In Transit**: TLS 1.2+ for all API calls

### Access Control
- IAM roles with least-privilege policies
- VPC endpoints for private access
- No public access

### Backup & Recovery
- **Point-in-Time Recovery**: Enabled on all tables
- **Retention**: 35 days
- **Cross-Region Replication**: Available for disaster recovery

---

## Monitoring & Alerting

### CloudWatch Metrics
- ConsumedReadCapacityUnits
- ConsumedWriteCapacityUnits
- ThrottledRequests
- SystemErrors
- UserErrors

### Alarms
- Throttling > 0 for 5 minutes
- Error rate > 1% for 5 minutes
- Latency p99 > 100ms

---

*Last Updated: January 2024*
*Version: 1.0*
