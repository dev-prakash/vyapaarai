# Store Detail Page Documentation

## Overview
The Store Detail Page (`https://www.vyapaarai.com/store/{storeId}`) provides a comprehensive view of a specific store, including store information, available products, and customer reviews.

**Example URL**: https://www.vyapaarai.com/store/STORE-01K5SBCNYJP5V4ZCP3EVYKH4KV

---

## Architecture

### Frontend Component
- **File**: `/frontend-pwa/src/pages/StoreDetailPage.tsx`
- **Route**: `/store/:storeId`
- **Framework**: React + TypeScript + Material-UI

### Backend API Endpoint
- **Endpoint**: `GET /api/v1/stores/{store_id}`
- **File**: `/backend/lambda-email-minimal/lambda_handler.py` (lines 2343-2491)
- **Lambda Function**: `vyaparai-api-prod`
- **URL**: `https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/stores/{store_id}`

---

## Page Layout

The page is organized into **three main tabs**:

### 1. Products Tab
Displays all available products from the store's inventory with shopping cart functionality.

### 2. About Store Tab
Shows store description, benefits, hours, and quick statistics.

### 3. Reviews Tab
Displays customer reviews and overall rating statistics.

---

## Database Tables Used

### Table 1: `vyaparai-stores-prod`

**Purpose**: Primary store information

**Primary Key**: `id` (String)

**Data Retrieved**:
| Field in DB | Field in API Response | Location on Page | Description |
|-------------|----------------------|------------------|-------------|
| `id` | `store.id` | URL parameter | Unique store identifier |
| `name` | `store.name` | Hero section (H3) | Store name |
| `phone` | `store.phone` | Hero section & Info bar | Contact phone number |
| `email` | `store.email` | Info bar | Contact email |
| `address` (JSON) | `store.address.*` | Hero section & Info bar | Full address with street, city, state, pincode |
| `settings.store_type` | `store.category` | Hero section (Chip) | Store category/type |
| `settings.description` | `store.description` | About Store tab | Store description text |
| `settings.tagline` | `store.tagline` | Hero section (H6) | Store tagline/slogan |
| `settings.business_hours.open` | Part of `store.openingHours` | Hero section & About tab | Opening time |
| `settings.business_hours.close` | Part of `store.openingHours` | Hero section & About tab | Closing time |
| `status` | `store.status` | Backend only | Store active status |
| `owner` | `store.owner` | Backend only | Store owner ID |

**Code Location**: `lambda_handler.py:2362-2377`

```python
store_response = dynamodb.get_item(
    TableName=TABLE_NAMES['stores'],
    Key={'id': {'S': store_id}}
)
```

**Settings JSON Structure**:
```json
{
  "store_type": "General Store",
  "description": "Welcome to our store! We offer a wide variety of quality products.",
  "tagline": "Your neighborhood store",
  "business_hours": {
    "open": "09:00",
    "close": "21:00"
  }
}
```

---

### Table 2: `vyaparai-inventory-prod`

**Purpose**: Store's inventory - links stores to products with quantity

**Global Secondary Index**: `store_id-index`

**Data Retrieved**:
| Field in DB | Usage | Location on Page |
|-------------|-------|------------------|
| `store_id` | Query key to find all inventory for this store | N/A (query parameter) |
| `product_id` | Used to fetch product details from products table | N/A (join key) |
| `quantity` | Determines stock availability | Products tab - "In Stock" / "Out of Stock" badge |

**Code Location**: `lambda_handler.py:2385-2424`

```python
inventory_response = dynamodb.query(
    TableName=TABLE_NAMES['inventory'],
    IndexName='store_id-index',
    KeyConditionExpression='store_id = :store_id',
    ExpressionAttributeValues={':store_id': {'S': store_id}},
    Limit=50
)
```

**Current Status**: ⚠️ Table not yet created - API handles gracefully by returning empty products array

---

### Table 3: `vyaparai-products-prod`

**Purpose**: Product catalog with details

**Primary Key**: `product_id` (String)

**Data Retrieved**:
| Field in DB | Field in API Response | Location on Page | Description |
|-------------|----------------------|------------------|-------------|
| `product_id` | `products[].id` | Products tab (card) | Unique product identifier |
| `name` | `products[].name` | Products tab - Card title (H6) | Product name |
| `price` | `products[].price` | Products tab - Large price (H5) | Product price in rupees |
| `description` | `products[].description` | Products tab - Card body text | Product description |
| `category` | `products[].category` | Backend only | Product category |
| `image_url` | `products[].image` | Products tab - Card image | Product image URL |
| `unit` | `products[].unit` | Products tab - Unit chip | Unit of measure (e.g., "1kg", "500ml") |

**Code Location**: `lambda_handler.py:2400-2418`

```python
product_response = dynamodb.get_item(
    TableName=TABLE_NAMES['products'],
    Key={'product_id': {'S': product_id}}
)
```

**Derived Fields**:
- `inStock`: Boolean calculated from `inventory.quantity > 0`
- `quantity`: From inventory table

**Current Status**: ⚠️ Table exists but no products linked to this store yet

---

### Table 4: `vyaparai-reviews-prod`

**Purpose**: Customer reviews and ratings

**Global Secondary Index**: `store_id-index`

**Data Retrieved**:
| Field in DB | Field in API Response | Location on Page | Description |
|-------------|----------------------|------------------|-------------|
| `review_id` | `reviews[].id` | Reviews tab | Unique review identifier |
| `store_id` | Query key | N/A (query parameter) | Links review to store |
| `customer_name` | `reviews[].customer_name` | Reviews tab - Avatar & name | Customer's display name |
| `rating` | `reviews[].rating` | Reviews tab - Star rating | 1-5 star rating |
| `comment` | `reviews[].comment` | Reviews tab - Review text | Customer's review text |
| `created_at` | `reviews[].created_at` | Reviews tab - Date | Review submission date |

**Code Location**: `lambda_handler.py:2426-2451`

```python
reviews_response = dynamodb.query(
    TableName=TABLE_NAMES['reviews'],
    IndexName='store_id-index',
    KeyConditionExpression='store_id = :store_id',
    ExpressionAttributeValues={':store_id': {'S': store_id}},
    Limit=100
)
```

**Aggregated Calculations**:
- `average_rating`: Calculated from all reviews' ratings (sum / count)
- `rating_count`: Total number of reviews for this store

**Rating Display**:
- Hero section: Star rating + average (e.g., "4.5 ⭐⭐⭐⭐⭐ (23 reviews)")
- Reviews tab: Large aggregate display + individual review cards

**Current Status**: ⚠️ Table not yet created - API returns rating=0, rating_count=0

---

## API Response Structure

### Success Response (200 OK)

```json
{
  "success": true,
  "store": {
    "id": "STORE-01K5SBCNYJP5V4ZCP3EVYKH4KV",
    "name": "Morning Star Bakery and General Store",
    "phone": "+919874563210",
    "email": "dev.prakash@gmail.com",
    "address": {
      "street": "Ground Flr, No. 584/187, Jail Rd, near Singh Hospital, Sector L, Bangla Bazar",
      "city": "Lucknow",
      "state": "Uttar Pradesh",
      "pincode": "226002",
      "full": "Ground Flr, No. 584/187, Jail Rd, near Singh Hospital, Sector L, Bangla Bazar, Lucknow, Uttar Pradesh 226002"
    },
    "category": "General Store",
    "description": "Welcome to our store! We offer a wide variety of quality products.",
    "tagline": "Your neighborhood store",
    "isOpen": true,
    "rating": 0,
    "rating_count": 0,
    "openingHours": "09:00 - 21:00",
    "owner": "",
    "status": "active",
    "products": [
      {
        "id": "PROD-123",
        "name": "Basmati Rice",
        "price": 120,
        "description": "Premium quality basmati rice",
        "category": "Grains",
        "image": "https://example.com/rice.jpg",
        "unit": "1kg",
        "inStock": true,
        "quantity": 50
      }
    ],
    "reviews": [
      {
        "id": "REV-456",
        "customer_name": "John Doe",
        "rating": 5,
        "comment": "Great store with quality products!",
        "created_at": "2025-10-20T10:30:00Z"
      }
    ],
    "total_products": 1
  }
}
```

### Error Responses

**404 Not Found**:
```json
{
  "detail": "Store not found"
}
```

**500 Internal Server Error**:
```json
{
  "detail": "Error: [error message]"
}
```

---

## Page Components Breakdown

### Hero Section (Gradient Background)
**Data Sources**:
- Store name → `vyaparai-stores-prod.name`
- Store tagline → `vyaparai-stores-prod.settings.tagline`
- Rating → Calculated from `vyaparai-reviews-prod`
- Category chip → `vyaparai-stores-prod.settings.store_type`
- Open/Closed status → `vyaparai-stores-prod.isOpen` (TODO: Calculate from business_hours)
- Opening hours → `vyaparai-stores-prod.settings.business_hours`

**Actions**:
- Call button → Uses `vyaparai-stores-prod.phone`
- Directions button → Uses `vyaparai-stores-prod.address`
- Email button → Uses `vyaparai-stores-prod.email`

---

### Info Bar (Below Hero)
**Data Sources**:
- Address → `vyaparai-stores-prod.address.full`
- Phone → `vyaparai-stores-prod.phone`
- Total products → Count of `products` array from `vyaparai-inventory-prod`

---

### Products Tab
**Data Sources**:
- Product grid → Query `vyaparai-inventory-prod` by `store_id`
- For each inventory item, fetch from `vyaparai-products-prod`
- Stock status → `vyaparai-inventory-prod.quantity > 0`

**Features**:
- Add to cart functionality (localStorage)
- Product image or emoji placeholder
- Price display in ₹ (Rupees)
- Out of stock badge
- Unit display (kg, L, dozen, etc.)

**Empty State**:
"This store hasn't added any products yet. Please check back later!"

---

### About Store Tab

#### Left Panel (Main Content)
**Data Sources**:
- Store description → `vyaparai-stores-prod.settings.description`
- Benefits section → Static UI with icons

#### Right Panel (Sidebar)

**Store Hours Card**:
- Opening hours → `vyaparai-stores-prod.settings.business_hours`

**Quick Stats Card**:
- Products count → `total_products` from API
- Reviews count → `rating_count` from API
- Average rating → `rating` from API

---

### Reviews Tab

#### Aggregate Rating Display
**Data Sources**:
- Average rating (large number) → Calculated from `vyaparai-reviews-prod`
- Star rating visual → Based on average
- Total reviews count → Count of reviews
- Text: "Based on X reviews"

#### Individual Review Cards
**Data Sources** (for each review from `vyaparai-reviews-prod`):
- Customer avatar → First letter of `customer_name`
- Customer name → `customer_name`
- Star rating → `rating` (1-5)
- Review text → `comment`
- Date → `created_at` (formatted)

**Empty State**:
"No reviews yet. Be the first to review this store!"

---

### Floating Cart (Bottom)
**Data Sources**:
- Cart items → localStorage (client-side)
- Product details → From loaded products array
- Total price → Calculated from cart × product prices

**Functionality**:
- Shows only when cart has items
- Displays item count and total price
- Checkout button navigates to `/checkout`

---

## User Interactions

### 1. Viewing Products
**Flow**:
1. User clicks on store from nearby stores list
2. Frontend calls `GET /api/v1/stores/{store_id}`
3. Backend queries:
   - `vyaparai-stores-prod` for store info
   - `vyaparai-inventory-prod` for store's products
   - `vyaparai-products-prod` for each product's details
   - `vyaparai-reviews-prod` for ratings
4. Frontend displays data in three tabs

### 2. Adding Products to Cart
**Flow**:
1. User clicks "Add to Cart" on a product
2. Product added to localStorage cart
3. Floating cart appears/updates
4. User can increment/decrement quantities

### 3. Checkout
**Flow**:
1. User clicks "Checkout" on floating cart
2. Navigate to `/checkout` with state:
   - Store information
   - Cart items (product + quantity)
   - Total price
3. Customer completes order

### 4. Contacting Store
**Flow**:
- **Call**: Opens phone dialer with `tel:{phone}`
- **Email**: Opens email client with `mailto:{email}`
- **Directions**: Opens Google Maps with store address

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  User Browser                                │
│  https://www.vyapaarai.com/store/STORE-01K5SBCNYJP5V4ZCP... │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ GET /api/v1/stores/{store_id}
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda: vyaparai-api-prod                       │
│         lambda_handler.get_store_details()                   │
└──┬────────────┬────────────┬────────────┬───────────────────┘
   │            │            │            │
   │ GetItem    │ Query      │ GetItem    │ Query
   │ by id      │ by GSI     │ by key     │ by GSI
   ▼            ▼            ▼            ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  stores  │ │inventory │ │ products │ │ reviews  │
│  -prod   │ │  -prod   │ │  -prod   │ │  -prod   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
     │            │            │            │
     │            │            │            │
     └────────────┴────────────┴────────────┘
                  │
                  │ Aggregate & Format
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                     API Response                             │
│  {success: true, store: {...}, products: [...], reviews:[]} │
└─────────────────────────────────────────────────────────────┘
```

---

## Current Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Frontend Page | ✅ Complete | StoreDetailPage.tsx fully implemented |
| Backend API Endpoint | ✅ Complete | GET /api/v1/stores/{store_id} working |
| Store Info Display | ✅ Working | Data from vyaparai-stores-prod |
| Products Tab | ⚠️ Ready | API ready, no inventory/products data yet |
| Reviews Tab | ⚠️ Ready | API ready, reviews table doesn't exist yet |
| About Store Tab | ✅ Working | Uses store settings |
| Cart Functionality | ✅ Working | localStorage-based cart |
| Error Handling | ✅ Complete | Graceful fallbacks for missing tables |
| Routing | ✅ Working | /store/:storeId route active |
| Responsive Design | ✅ Complete | Mobile-first Material-UI layout |

---

## Missing Database Tables

### 1. `vyaparai-inventory-prod`
**Status**: Not created

**Schema Needed**:
```
Partition Key: inventory_id (String)
Sort Key: None
GSI: store_id-index
  - Partition Key: store_id
  - Sort Key: None
```

**Sample Data**:
```json
{
  "inventory_id": "INV-001",
  "store_id": "STORE-01K5SBCNYJP5V4ZCP3EVYKH4KV",
  "product_id": "PROD-123",
  "quantity": 50,
  "last_updated": "2025-10-23T10:00:00Z"
}
```

### 2. `vyaparai-reviews-prod`
**Status**: Not created

**Schema Needed**:
```
Partition Key: review_id (String)
Sort Key: None
GSI: store_id-index
  - Partition Key: store_id
  - Sort Key: created_at (for sorting by date)
```

**Sample Data**:
```json
{
  "review_id": "REV-001",
  "store_id": "STORE-01K5SBCNYJP5V4ZCP3EVYKH4KV",
  "customer_id": "CUST-123",
  "customer_name": "John Doe",
  "rating": 5,
  "comment": "Excellent service and fresh products!",
  "created_at": "2025-10-23T10:30:00Z"
}
```

---

## Rating Calculation Logic

### In Nearby Stores API (`/api/v1/stores/nearby`)

**Code Location**: `lambda_handler.py:2301`

```python
# Get real rating from reviews
rating, rating_count = await get_store_rating(store_id)

store = {
    ...
    'rating': rating if rating > 0 else None,
    'rating_count': rating_count,
    ...
}
```

### Helper Function

**Code Location**: `lambda_handler.py:2495-2523`

```python
async def get_store_rating(store_id: str) -> tuple[float, int]:
    """Get average rating and count for a store"""
    try:
        dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

        reviews_response = dynamodb.query(
            TableName=TABLE_NAMES['reviews'],
            IndexName='store_id-index',
            KeyConditionExpression='store_id = :store_id',
            ExpressionAttributeValues={':store_id': {'S': store_id}},
            ProjectionExpression='rating',
            Limit=100
        )

        total_rating = 0
        rating_count = 0

        for review_item in reviews_response.get('Items', []):
            rating = int(review_item.get('rating', {}).get('N', '0'))
            if rating > 0:
                total_rating += rating
                rating_count += 1

        average_rating = round(total_rating / rating_count, 1) if rating_count > 0 else 0
        return (average_rating, rating_count)

    except Exception as e:
        logger.warning(f"Error calculating rating for store {store_id}: {e}")
        return (0, 0)
```

**Behavior**:
- If reviews table doesn't exist: Returns (0, 0)
- If no reviews: Returns (0, 0)
- If reviews exist: Returns (average rounded to 1 decimal, count)
- Only includes ratings 1-5 in calculation

---

## Security & Permissions

### Required IAM Permissions

The Lambda execution role needs:

```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:GetItem",
    "dynamodb:Query"
  ],
  "Resource": [
    "arn:aws:dynamodb:ap-south-1:*:table/vyaparai-stores-prod",
    "arn:aws:dynamodb:ap-south-1:*:table/vyaparai-stores-prod/index/*",
    "arn:aws:dynamodb:ap-south-1:*:table/vyaparai-inventory-prod",
    "arn:aws:dynamodb:ap-south-1:*:table/vyaparai-inventory-prod/index/*",
    "arn:aws:dynamodb:ap-south-1:*:table/vyaparai-products-prod",
    "arn:aws:dynamodb:ap-south-1:*:table/vyaparai-reviews-prod",
    "arn:aws:dynamodb:ap-south-1:*:table/vyaparai-reviews-prod/index/*"
  ]
}
```

---

## Performance Considerations

### API Response Time
- **Store info**: Single GetItem (fast, ~10ms)
- **Products**: Query inventory + N GetItem calls for products (slower if many products)
- **Reviews**: Single Query, limited to 100 reviews (fast, ~20ms)

**Total typical response time**: 50-200ms

### Optimization Opportunities

1. **Batch GetItem**: Use `batch_get_item` for products instead of N individual calls
2. **Caching**: Add Redis/ElastiCache for store details (rarely change)
3. **Pagination**: Add pagination for products and reviews
4. **Lazy Loading**: Load reviews only when Reviews tab is clicked (frontend optimization)

---

## Future Enhancements

### Phase 1 (Data Population)
- [ ] Create and populate `vyaparai-inventory-prod` table
- [ ] Create and populate `vyaparai-reviews-prod` table
- [ ] Add real product images to `vyaparai-products-prod`

### Phase 2 (Features)
- [ ] Add review submission functionality
- [ ] Implement business hours calculation for isOpen status
- [ ] Add store images/photos gallery
- [ ] Add special offers/promotions section
- [ ] Add store owner response to reviews

### Phase 3 (Advanced)
- [ ] Real-time inventory updates via WebSocket
- [ ] Store analytics dashboard
- [ ] Recommendation engine for products
- [ ] Multi-language support for store descriptions

---

## Testing

### Manual Testing Commands

**Test Store Detail API**:
```bash
curl "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/stores/STORE-01K5SBCNYJP5V4ZCP3EVYKH4KV"
```

**Test Nearby Stores API**:
```bash
curl "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/stores/nearby?city=Lucknow&state=Uttar%20Pradesh"
```

### Test Scenarios

1. **Valid Store ID**: Should return complete store details
2. **Invalid Store ID**: Should return 404 error
3. **Store with no products**: Should return empty products array
4. **Store with no reviews**: Should return rating=0, rating_count=0
5. **Non-existent inventory table**: Should gracefully handle and return empty products

---

## Support & Troubleshooting

### Common Issues

**Issue**: Store page shows "Store not found"
- **Cause**: Invalid store_id or store doesn't exist in database
- **Solution**: Verify store_id exists in `vyaparai-stores-prod`

**Issue**: Products tab is empty
- **Cause**: No inventory records or inventory table doesn't exist
- **Solution**: Add inventory records linking store_id to product_id

**Issue**: Rating shows 0
- **Cause**: No reviews exist or reviews table not created
- **Solution**: Create `vyaparai-reviews-prod` table and add reviews

**Issue**: 502 Bad Gateway error
- **Cause**: Lambda function failing (usually missing dependencies)
- **Solution**: Check CloudWatch logs, ensure all Python packages deployed

---

## Related Documentation

- **API Endpoints**: `/docs/api-documentation.md`
- **Database Schema**: `/docs/database-schema.md`
- **Frontend Components**: `/docs/frontend-architecture.md`
- **Deployment Guide**: `/docs/deployment-guide.md`

---

**Document Version**: 1.0
**Last Updated**: October 23, 2025
**Author**: Claude (AI Assistant)
**Status**: Production Deployed ✅
