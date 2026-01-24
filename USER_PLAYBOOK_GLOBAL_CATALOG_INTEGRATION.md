# Global Catalog Integration - User Guide

## What Changed
Store owners can now add products from the global catalog directly to their inventory with custom pricing and stock levels. This feature resolves the "Failed to add product to inventory" error that was previously occurring.

## Who Is Affected
- [x] Store Owners
- [ ] Customers
- [ ] Admins
- [ ] All Users

## New Behavior

### Before
- Store owners experienced "Failed to add product to inventory" errors when trying to add global catalog products
- The frontend would make API calls to a non-existent endpoint (`/products/from-catalog`)
- No way to easily add pre-existing products from the centralized catalog

### After
- Store owners can successfully add any product from the global catalog to their inventory
- Custom pricing can be set for each product (different from global catalog pricing)
- Initial stock levels and inventory management settings can be configured
- Complete integration with existing inventory management system

## How To Use

### Step 1: Access Inventory Management
1. Log in to your store owner dashboard
2. Navigate to the **Inventory** section
3. Click on **Add Product** or **Add from Catalog**

### Step 2: Select from Global Catalog
1. In the product entry form, choose **"Add from Global Catalog"** option
2. Browse or search the available products in the global catalog
3. Select the product you want to add to your inventory

### Step 3: Configure Store-Specific Details
1. **Selling Price**: Set your store's selling price (required)
2. **Cost Price**: Enter what you paid for the product (optional)
3. **Initial Stock**: Set how many units you currently have
4. **Stock Thresholds**:
   - **Minimum Level**: Low stock alert threshold (default: 10)
   - **Maximum Level**: Maximum capacity (default: 100)
   - **Reorder Point**: When to reorder (default: 10)
5. **Location**: Where the product is stored in your shop
6. **Notes**: Any additional information about the product

### Step 4: Save and Confirm
1. Review all entered information
2. Click **"Add to Inventory"**
3. Confirm the product appears in your inventory list

## Common Scenarios

### Scenario 1: Adding Popular FMCG Product
1. Search for "Maggi Noodles" in the global catalog
2. Select the 2-minute variety
3. Set selling price: ₹15 (vs global MRP: ₹12)
4. Set initial stock: 50 units
5. Set location: "Shelf A-2"
6. Add notes: "Popular item - reorder weekly"
7. **Expected Result**: Product added successfully with custom pricing

### Scenario 2: Adding Product with Different Pricing Strategy
1. Find "Britannia Good Day Biscuits" in global catalog
2. Set competitive selling price: ₹25
3. Set cost price: ₹20 (for profit tracking)
4. Set stock: 25 units
5. Set reorder point: 5 (fast-moving item)
6. **Expected Result**: Product available for sale with your pricing strategy

### Scenario 3: Bulk Addition of Common Items
1. Add multiple products in sequence:
   - Rice (Basmati) - 100kg stock
   - Wheat Flour - 50kg stock
   - Cooking Oil - 20 bottles
2. Set appropriate pricing for each
3. **Expected Result**: Complete grocery section setup in inventory

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Product already exists" error | Product already in your inventory | Check existing inventory or use update function |
| "Global product not found" error | Invalid product selection | Refresh catalog and try again |
| "Valid selling price required" error | Missing or zero selling price | Enter a positive selling price |
| "Authentication failed" error | Session expired | Log out and log back in |
| Page not responding | Network connectivity | Check internet connection and retry |

## FAQ

**Q: Can I modify the product details after adding from the catalog?**
A: Yes, you can update pricing, stock levels, and other store-specific details anytime through the inventory management interface.

**Q: Will the global catalog price affect my selling price?**
A: No, your selling price is completely independent. The global catalog provides product information (name, brand, category) but you set your own pricing.

**Q: What happens if a product is removed from the global catalog?**
A: Your inventory record remains intact. Only the link to global catalog data is affected. Your pricing and stock information are preserved.

**Q: Can I add the same product multiple times?**
A: No, each product can only exist once in your inventory. If you try to add an existing product, you'll get a "Product already exists" error.

**Q: How do I know which products are available in the global catalog?**
A: The global catalog contains 95+ real Indian retail products including popular FMCG items, groceries, household goods, and local products.

**Q: Is there a limit to how many products I can add?**
A: No, you can add as many products as you need for your store. The system is designed to handle large inventories efficiently.

**Q: Can customers see products I've added from the global catalog?**
A: Yes, once added to your inventory with `is_active: true`, customers can discover and order these products from your store.

**Q: What's the difference between adding a custom product vs. adding from catalog?**
A: Custom products are unique to your store. Catalog products benefit from standardized information (proper names, categories, brand details) and may have better search visibility.

---

## Technical Notes for Advanced Users

### API Endpoint
- **Endpoint**: `POST /api/v1/inventory/products/from-catalog`
- **Authentication**: Store owner JWT token required
- **Rate Limiting**: Standard API rate limits apply

### Data Integration
- Global catalog data is automatically mapped to your inventory
- Product source is marked as 'global_catalog' for tracking
- All financial calculations use precise decimal arithmetic

### Performance
- Product addition typically completes in under 500ms
- Real-time inventory updates across all systems
- Async processing for optimal user experience

---

## Related Documentation
- [Technical Design Document](TECHNICAL_DESIGN_DOCUMENT.md) - Section 17.4
- [Store Owner Playbook](frontend-pwa/docs/USER_PLAYBOOK_STORE_OWNER.md) - General inventory management
- [API Documentation](backend/README.md) - Complete API reference

---

**Last Updated**: January 18, 2026
**Version**: 1.0
**Author**: Dev Prakash

*For support: dev@vyaparai.com*