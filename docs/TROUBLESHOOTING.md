# VyapaarAI Troubleshooting Guide

## Common Issues and Solutions

### Customer Login - TypeError: Cannot read properties of undefined (reading 'length')

**Issue Date:** December 2, 2025
**Status:** RESOLVED
**Severity:** Critical

#### Problem Description

When customers log in and are redirected to `/customer/stores`, the application crashes with:
```
TypeError: Cannot read properties of undefined (reading 'length')
```

#### Root Cause

The `StoreSelector` component in `frontend-pwa/src/pages/customer/StoreSelector.tsx` was accessing `nearbyStores.length` and using array methods like `.filter()` without defensive null checking. In certain scenarios (e.g., slow network, race conditions), the `nearbyStores` from `useStore()` context could be `undefined` instead of an empty array `[]`.

#### Solution Implemented

Added defensive null checking at all locations where `nearbyStores` is accessed:

**File:** `frontend-pwa/src/pages/customer/StoreSelector.tsx`

1. **Line 213** - Filter stores safely:
```typescript
// Before:
const filteredStores = nearbyStores.filter((store) => ...)

// After:
const filteredStores = (nearbyStores || []).filter((store) => ...)
```

2. **Line 241** - Display store count safely:
```typescript
// Before:
{nearbyStores.length} stores nearby

// After:
{nearbyStores?.length ?? 0} stores nearby
```

3. **Line 575** - Conditional rendering:
```typescript
// Before:
{hasSearched && nearbyStores.length > 0 && (

// After:
{hasSearched && (nearbyStores?.length ?? 0) > 0 && (
```

4. **Lines 594, 605** - Filter operations:
```typescript
// Before:
{nearbyStores.filter((s) => s.isOpen).length}
{nearbyStores.filter((s) => s.rating && s.rating >= 4).length}

// After:
{(nearbyStores || []).filter((s) => s.isOpen).length}
{(nearbyStores || []).filter((s) => s.rating && s.rating >= 4).length}
```

#### Verification Steps

After deployment, verify the fix:

1. Open browser console (F12)
2. Navigate to https://www.vyapaarai.com
3. Check build tag: `window.VyapaarAI_BUILD_TAG`
4. Expected value: `STORE_NULL_FIX_BUILD_2025-12-02T22:20:00Z_FORCE_REFRESH`

#### If Issue Persists - Browser Cache Clearing

If you still see the error after deployment, clear browser cache:

**Chrome/Edge:**
1. Press `Ctrl+Shift+Delete` (Windows) or `Cmd+Shift+Delete` (Mac)
2. Select "Cached images and files"
3. Click "Clear data"
4. **Hard refresh:** `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)

**Firefox:**
1. Press `Ctrl+Shift+Delete` (Windows) or `Cmd+Shift+Delete` (Mac)
2. Select "Cache"
3. Click "Clear Now"
4. **Hard refresh:** `Ctrl+F5` (Windows) or `Cmd+Shift+R` (Mac)

**Safari:**
1. `Safari > Preferences > Advanced`
2. Enable "Show Develop menu in menu bar"
3. `Develop > Empty Caches`
4. **Hard refresh:** `Cmd+Option+R`

**Mobile (iOS):**
1. Settings > Safari > Clear History and Website Data
2. Restart browser

**Mobile (Android Chrome):**
1. Settings > Privacy > Clear browsing data
2. Select "Cached images and files"
3. Restart browser

#### Service Worker Issues

The application uses a service worker for offline functionality. If cache clearing doesn't work:

1. Open DevTools (F12)
2. Go to "Application" tab (Chrome) or "Storage" tab (Firefox)
3. Click "Service Workers" (Chrome) or "Service Workers" under "Application" (Firefox)
4. Click "Unregister" for all VyapaarAI service workers
5. Go to "Cache Storage"
6. Delete all caches starting with "workbox-"
7. Hard refresh the page

---

## Deployment Checklist

When deploying frontend fixes:

1. ✅ **Update Build Tag** in `frontend-pwa/src/App.tsx`
   ```typescript
   const BUILD_TAG = 'DESCRIPTIVE_NAME_BUILD_YYYY-MM-DDTHH:MM:SSZ'
   ```

2. ✅ **Build Frontend**
   ```bash
   cd frontend-pwa
   npm run build
   ```

3. ✅ **Deploy to S3**
   ```bash
   # Deploy assets with long cache
   aws s3 sync dist/ s3://www.vyapaarai.com/ --delete \
     --cache-control "public, max-age=31536000, immutable" \
     --exclude "index.html" --exclude "sw.js" \
     --exclude "manifest.webmanifest" --exclude "registerSW.js"

   # Deploy HTML/SW with no cache
   aws s3 cp dist/index.html s3://www.vyapaarai.com/index.html \
     --cache-control "public, max-age=0, must-revalidate"
   aws s3 cp dist/sw.js s3://www.vyapaarai.com/sw.js \
     --cache-control "public, max-age=0, must-revalidate"
   aws s3 cp dist/manifest.webmanifest s3://www.vyapaarai.com/manifest.webmanifest \
     --cache-control "public, max-age=0, must-revalidate"
   aws s3 cp dist/registerSW.js s3://www.vyapaarai.com/registerSW.js \
     --cache-control "public, max-age=0, must-revalidate"
   ```

4. ✅ **Invalidate CloudFront Cache**
   ```bash
   aws cloudfront create-invalidation --distribution-id E1UY93SVXV8QOF --paths "/*"
   ```

5. ✅ **Verify Deployment**
   ```bash
   # Check invalidation status
   aws cloudfront get-invalidation --distribution-id E1UY93SVXV8QOF --id <INVALIDATION_ID>
   ```

6. ✅ **Test in Browser**
   - Open https://www.vyapaarai.com
   - Check build tag in console
   - Test affected functionality

---

## Context Provider Issues

### StoreContext Not Available

**Error:**
```
Error: useStore must be used within a StoreProvider
```

**Solution:**
Ensure `StoreProvider` is wrapping your component in the provider hierarchy.

**Provider Hierarchy:** (defined in `frontend-pwa/src/providers/AppProviders.tsx` and `frontend-pwa/src/contexts/index.tsx`)
```
<AppProviders>          // Main app providers
  <StoreProvider>       // Store context (included in contexts/index.tsx AppProvider)
    <OrderProvider>     // Order context
      <YourComponent />
    </OrderProvider>
  </StoreProvider>
</AppProviders>
```

**Verification:**
Check `frontend-pwa/src/main.tsx`:
```typescript
<AppProviders>
  <App />
</AppProviders>
```

And `frontend-pwa/src/providers/AppProviders.tsx`:
```typescript
import { AppProvider as EcommerceContextProvider } from '../contexts'
// ...
<EcommerceContextProvider>
  {children}
</EcommerceContextProvider>
```

---

## API and Backend Issues

### Nearby Store Search Returns No Results

**Issue Date:** February 10, 2026
**Status:** RESOLVED
**Severity:** High

#### Problem Description

Visiting `www.vyapaarai.com/nearby-stores` and searching by Address with State="Uttar Pradesh" and City="Lucknow" returned no results, even though a store exists in the `vyaparai-stores-prod` DynamoDB table.

#### Root Cause

Two bugs in `backend/app/api/v1/stores.py`:

1. **DynamoDB `Limit` parameter misuse**: The `list_stores` endpoint passed `Limit=500` directly to `stores_table.scan()`. DynamoDB's `Limit` caps the number of items **scanned** (evaluated), not the number of items **returned** after `FilterExpression`. With `status = active` as a filter, if the table has 500+ items and the target store appears after position 500 in the scan, it would never be returned. Additionally, `LastEvaluatedKey` pagination was not implemented, so only the first page of results was ever returned.

2. **`float(None)` TypeError**: Some store records had `latitude`/`longitude` keys present but set to `None`. The code used `float(item.get('latitude', 0)) if 'latitude' in item else None`, which called `float(None)` and crashed with `TypeError: float() argument must be a string or a real number, not 'NoneType'`.

#### Solution Implemented

**File:** `backend/app/api/v1/stores.py`

1. **Pagination fix**: Replaced single non-paginated scan with a pagination loop using `LastEvaluatedKey`/`ExclusiveStartKey`. Removed `Limit` parameter from scan kwargs. Added early-stop when enough results are collected.

2. **None lat/lng fix**: Changed from:
```python
"latitude": float(item.get('latitude', 0)) if 'latitude' in item else None,
```
To:
```python
"latitude": float(item['latitude']) if item.get('latitude') is not None else None,
```

#### Related: Stats Table Naming Inconsistency

A secondary issue was discovered: two DynamoDB tables existed (`vyaparai-store-stats-prod` and `vyaparai-store-stats-production`) due to Lambda setting `ENVIRONMENT=production` while Terraform defaults to `prod`. Fixed by:
- Adding `STATS_TABLE` constant in `backend/app/core/database.py` defaulting to `vyaparai-store-stats-production`
- Updating `backend/app/database/stats_repository.py` to use the central constant
- The empty `vyaparai-store-stats-prod` table can be safely deleted from AWS

#### Verification

```bash
# Test list_stores returns all active stores
curl -s "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/stores/list?limit=500"

# Test nearby search for Lucknow, UP
curl -s "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/stores/nearby?city=Lucknow&state=Uttar+Pradesh"
```

---

### Market Prices API Not Loading

**Issue:** Market prices showing "Market prices unavailable"

**Common Causes:**
1. Lambda function not deployed with correct dependencies
2. data.gov.in API is down or slow
3. Missing environment variables

**Solution:**

1. **Check Lambda has httpx dependency:**
   ```bash
   cd backend
   grep httpx requirements.txt
   # Should show: httpx>=0.25.0
   ```

2. **Verify Lambda environment variables:**
   ```bash
   aws lambda get-function-configuration --function-name vyaparai-backend-prod \
     --query 'Environment.Variables' --output json
   ```
   Should include:
   ```json
   {
     "DATA_GOV_API_KEY": "...",
     "DYNAMODB_TABLE_NAME": "market_prices_cache"
   }
   ```

3. **Test API directly:**
   ```bash
   curl "https://api.vyaparai.com/api/v1/public/market-prices?commodities=Tomato,Onion"
   ```

4. **Check Lambda logs:**
   ```bash
   aws logs tail /aws/lambda/vyaparai-backend-prod --follow
   ```

---

## Build and Deployment Issues

### Large Bundle Size Warning

**Warning:**
```
(!) Some chunks are larger than 1000 kB after minification.
```

**Status:** Known issue, not critical

**Future Optimization:**
- Implement code splitting with dynamic imports
- Use `build.rollupOptions.output.manualChunks`
- Consider lazy loading heavy components

### Service Worker Not Updating

**Issue:** Changes not reflected after deployment

**Solution:**
1. Increment version in `frontend-pwa/vite.config.ts` (if using workbox plugin versioning)
2. Clear service worker in DevTools
3. Main.tsx already includes auto-cleanup:
```typescript
// Force cache refresh for this deployment
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then(registrations => {
    registrations.forEach(registration => {
      registration.unregister()
    })
  })
}
```

---

### Guest Checkout - Cart Empty on Checkout Page

**Issue Date:** February 11, 2026
**Status:** RESOLVED
**Severity:** Critical

#### Problem Description

Guest customers (not logged in) could add products to cart on the Store Detail Page (`/store/{storeId}`), but when clicking "Checkout", the `/checkout` page showed an empty cart with ₹0 total.

#### Root Cause

The `StoreDetailPage.tsx` used only local React state (`useState({})`) for cart management. When navigating to `/checkout`, the `CustomerCheckout.tsx` component reads cart data from the global Zustand store (`useCartStore`), which was never populated by the store page.

**Cart state disconnect:**
- `StoreDetailPage.tsx` → local `useState` only
- `CustomerCheckout.tsx` → reads from `useCartStore` (Zustand, persisted in localStorage)
- No bridge between the two → checkout always shows empty cart

#### Solution Implemented

**File:** `frontend-pwa/src/pages/StoreDetailPage.tsx`

1. Imported `useCartStore` from `'../stores/cartStore'`
2. On component mount, set store context: `useCartStore.getState().setStoreId(storeId)`
3. In `handleAddToCart` and `handleRemoveFromCart`, sync cart changes to Zustand store via `useCartStore.setState()` alongside local state updates
4. Simplified `handleCheckout` to just `navigate('/checkout')` since Zustand is now the source of truth

**Key implementation detail:** Used direct `useCartStore.setState()` instead of `cartStore.addItem()` because the latter does a backend API sync and rolls back on failure for guest users.

#### Verification

1. Navigate to any store page (e.g., `https://www.vyapaarai.com/store/STORE-01KFSG8S99QMDCC0SKK47Q01JB`)
2. Add 3+ products to cart
3. Open browser console → `JSON.parse(localStorage.getItem('vyaparai-cart'))`
4. Verify items array has all added products with correct quantities
5. Click "Checkout" → verify checkout page shows all items with correct totals

---

### Guest Checkout - Order Creation TypeError (float * Decimal)

**Issue Date:** February 11, 2026
**Status:** RESOLVED
**Severity:** Critical

#### Problem Description

When placing an order, the backend returned:
```
Order creation failed: unsupported operand type(s) for *: 'float' and 'decimal.Decimal'
```

#### Root Cause

In `backend/app/api/v1/orders.py` line 1349, the GST fallback calculation (used when the GST service fails to find product HSN codes) mixed Python `float` and `decimal.Decimal` types:

```python
# BUG: subtotal is float, Decimal('0.18') is Decimal → TypeError
tax_amount = float(subtotal * Decimal('0.18'))
```

The `subtotal` variable was a `float` (from `sum(float * float)` price calculations), but `Decimal('0.18')` is a `Decimal`. Python does not allow `float * Decimal` arithmetic.

#### Solution Implemented

**File:** `backend/app/api/v1/orders.py` line 1349

```python
# Before:
tax_amount = float(subtotal * Decimal('0.18'))

# After:
tax_amount = float(Decimal(str(subtotal)) * Decimal('0.18'))
```

Converts `subtotal` to `Decimal` via string representation first, ensuring both operands are `Decimal` type.

#### Verification

```bash
# Place a test order via API
curl -X POST "https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com/api/v1/orders/" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: test-session" \
  -d '{
    "store_id": "STORE-01KFSG8S99QMDCC0SKK47Q01JB",
    "customer_name": "Test User",
    "customer_phone": "9876543210",
    "delivery_address": "Test Address",
    "items": [{"product_name": "Test Product", "unit_price": 100, "quantity": 1}],
    "payment_method": "cod"
  }'
```

---

### Guest Checkout - Missing product_id in Order Items

**Issue Date:** February 11, 2026
**Status:** RESOLVED
**Severity:** High

#### Problem Description

After fixing the Decimal TypeError, orders failed with:
```
Missing product_id in item: {'product_id': None, 'quantity_change': -1}
```

#### Root Cause

The `CustomerCheckout.tsx` was not including `product_id` in the order items payload sent to the backend. The backend's `order_transaction_service.create_order_with_stock_reservation()` uses the saga pattern and needs `product_id` to reserve stock (decrement inventory). Without it, the `inventory_service.update_stock_bulk_transactional()` rejects items with `None` product_id.

#### Solution Implemented

**File:** `frontend-pwa/src/pages/CustomerCheckout.tsx`

Added `product_id` to the items mapping in `handlePlaceOrder`:

```typescript
items: items.map(item => ({
  product_id: item.id || undefined,  // Added this field
  product_name: item.name,
  quantity: item.quantity,
  unit_price: item.price,
  unit: item.unit || 'pieces',
})),
```

#### Additional Fixes in CustomerCheckout.tsx

| Fix | Description |
|-----|-------------|
| **Store ID** | Changed from hardcoded `'store_123'` to dynamic `useCartStore().storeId` |
| **City/State/Pincode** | Added form fields for city, state, pincode (was hardcoded to Mumbai/Maharashtra/400001) |
| **API URL** | Direct `fetch()` to `API_BASE_URL + '/api/v1/orders/'` bypassing broken `orderService` path |
| **Request payload** | Transformed to match backend `CreateOrderRequest` schema (snake_case fields) |

---

### Store Detail Page - No Products Displayed

**Issue Date:** February 10, 2026
**Status:** RESOLVED
**Severity:** High

#### Problem Description

Store detail page at `/store/{storeId}` showed store information but no products, displaying "No products available" even though the store has products in inventory.

#### Root Cause

The `GET /api/v1/stores/{store_id}` endpoint was querying the `vyaparai-products-prod` table which only contains product master data (catalog), not the actual store inventory. The store's products are stored in `vyaparai-inventory-prod` (or `vyaparai-store-inventory-prod`) with `store_id` as partition key.

#### Solution Implemented

**File:** `backend/app/api/v1/stores.py`

Updated the store detail endpoint to query the inventory table instead of the products table, and properly transform inventory items into the product format expected by the frontend.

---

## Contact and Support

For issues not covered here:
1. Check application logs in browser console
2. Check backend Lambda logs: `aws logs tail /aws/lambda/vyaparai-api-prod`
3. Review recent deployments and changes
4. Contact development team

---

**Last Updated:** February 11, 2026
**Document Version:** 1.2
