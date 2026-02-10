# VyapaarAI User Guide - Recent Updates

## What Changed
VyapaarAI has undergone significant improvements including a complete rebranding, enhanced email service, and new bulk inventory upload capabilities. These changes improve user experience, security, and operational efficiency.

## Who Is Affected
- [x] Store Owners
- [x] Customers (email communications)
- [x] Admins
- [x] All Users

---

## Update 1: Enhanced Branding and Email Experience

### What Changed
The platform has been rebranded from "VyaparAI" to "VyapaarAI" with professional email templates and enhanced security messaging.

### New Behavior

#### Before
- Basic text emails for authentication
- Simple brand name "VyaparAI"
- Generic error messages during login
- Plain email formatting

#### After
- Professional HTML email templates with modern branding
- Correct Hindi spelling "VyapaarAI" (व्यापार = Business/Trade)
- Enhanced security warnings and user education
- Improved error messages with actionable guidance
- Responsive email design for all devices

### How To Use

#### Enhanced Email Authentication Experience

**Step 1: Request Login Passcode**
1. Visit the VyapaarAI login page
2. Enter your registered email address
3. Click "Send Passcode"

**Step 2: Check Your Enhanced Email**
You'll receive a professionally designed email with:
- Clear VyapaarAI branding with gradient header
- Large, easy-to-read 6-digit passcode
- 15-minute expiry countdown
- Security warnings about phishing protection
- Professional footer with copyright information

**Step 3: Use Passcode for Login**
1. Copy the 6-digit code from your email
2. Enter it on the login page within 15 minutes
3. If you receive error messages, they now provide specific guidance:
   - "Please check your email for the 6-digit passcode and try again"
   - "Passcode expired. Please request a new one"
   - "Maximum attempts exceeded. Please try again later"

### Security Improvements

**Enhanced Email Security Features:**
- Clear one-time use messaging
- Phishing protection warnings
- VyapaarAI staff verification notice
- Professional communication standards

**What to Watch For:**
- ⚠️ Never share your passcode with anyone
- ⚠️ VyapaarAI staff will never ask for your passcode
- ⚠️ If you didn't request the passcode, ignore the email

---

## Update 2: CSV Bulk Inventory Upload

### What Changed
Store owners can now upload inventory in bulk using CSV files, with real-time progress tracking and comprehensive error reporting.

### New Behavior

#### Before
- Manual product entry one-by-one
- Time-consuming inventory management
- No bulk upload capabilities
- Difficulty managing large inventories

#### After
- Upload hundreds of products via CSV file
- Real-time progress tracking with percentage completion
- Comprehensive error reporting and validation
- Job cancellation and status monitoring
- Support for all product fields and attributes

### How To Use

#### Bulk Upload Process

**Step 1: Prepare Your CSV File**
Create a CSV file with the following columns:
```csv
product_name,brand,sku,barcode,cost_price,selling_price,mrp,current_stock,min_stock_level,category,tax_rate,discount_percentage,is_returnable,is_perishable
```

**Example CSV Content:**
```csv
Rice Basmati 1kg,Tata,SKU001,1234567890123,45.00,50.00,55.00,100,10,Groceries,5.0,0.0,true,false
Cooking Oil 1L,Fortune,SKU002,2345678901234,120.00,130.00,140.00,50,5,Cooking,12.0,5.0,true,false
Milk 500ml,Amul,SKU003,3456789012345,22.00,25.00,28.00,200,20,Dairy,0.0,0.0,true,true
```

**Step 2: Upload CSV File**
1. Log in to your VyapaarAI store dashboard
2. Navigate to **Inventory Management**
3. Click on **Bulk Upload**
4. Select **Upload CSV**
5. Choose your prepared CSV file
6. Configure upload options:
   - ✅ Skip Duplicates: Ignore existing SKUs
   - ✅ Auto Verify: Automatically mark products as verified
   - ✅ Notification Email: Get completion notification

**Step 3: Monitor Upload Progress**
- View real-time progress percentage
- See counts of processed, successful, and error rows
- Estimated completion time display
- Option to cancel if needed

**Step 4: Review Results**
After completion, you'll see:
- Total products processed successfully
- Number of duplicate products skipped
- Error count with detailed error report
- Download link for error report CSV (if any errors occurred)

### Common Scenarios

#### Scenario 1: Small Inventory Upload (< 100 products)
1. Prepare CSV with your product list
2. Upload file with default settings
3. Monitor progress (typically completes in 2-5 minutes)
4. Review summary for any errors
5. Check your inventory for successfully added products

#### Scenario 2: Large Inventory Upload (1000+ products)
1. Split large inventory into smaller files (recommended: 500 products per file)
2. Upload first batch with "Skip Duplicates" enabled
3. Monitor progress (may take 10-15 minutes per batch)
4. Review error report and fix data issues
5. Upload subsequent batches
6. Use job cancellation if needed for adjustments

#### Scenario 3: Update Existing Inventory
1. Export current inventory (if available)
2. Prepare CSV with updates to existing SKUs
3. Upload with "Skip Duplicates" disabled
4. Review which products were updated vs. created new

### Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Invalid CSV format" | Missing required columns | Ensure all required columns are present and named correctly |
| "Upload failed" | File too large | Split into smaller files (max 5,000 rows) |
| "Job stuck in processing" | System timeout | Cancel job and retry with smaller batch |
| "Many validation errors" | Invalid data types | Check number formats, boolean values (true/false) |
| "Duplicate SKU errors" | SKUs already exist | Enable "Skip Duplicates" option |

### FAQ

**Q: What's the maximum file size I can upload?**
A: Maximum 10MB file size or 5,000 products per upload.

**Q: Can I cancel an upload in progress?**
A: Yes, use the "Cancel Job" button. Processed products up to that point will remain in your inventory.

**Q: What happens if my file has errors?**
A: The system will process valid rows and generate an error report CSV for the problematic rows.

**Q: How do I know when my upload is complete?**
A: You'll see the completion status on the progress page, and receive an email notification if configured.

**Q: Can I upload product images via CSV?**
A: Not currently. Use the individual product editing interface to add images after bulk upload.

---

## Summary of Benefits

### For Store Owners
- **Faster Setup**: Bulk upload reduces setup time by 90%
- **Professional Communication**: Enhanced email experience builds trust
- **Better Error Handling**: Clear guidance reduces support needs
- **Progress Tracking**: Know exactly when your uploads will complete

### For Customers
- **Professional Experience**: Improved email communications from stores
- **Better Security**: Enhanced protection against phishing
- **Consistent Branding**: Professional VyapaarAI experience across all touchpoints

### For All Users
- **Enhanced Security**: Better protection through improved authentication
- **Improved Reliability**: Comprehensive testing prevents system issues
- **Professional Platform**: Complete rebranding reflects platform maturity

---

## Getting Help

If you encounter any issues with these new features:

1. **Check the troubleshooting sections above**
2. **Review error messages carefully** - they now provide specific guidance
3. **Contact VyapaarAI support** with specific error details
4. **Use the in-app help system** for quick guidance

---

**Last Updated**: February 10, 2026
**Version**: 1.0
**Applies To**: VyapaarAI Platform v3.1+