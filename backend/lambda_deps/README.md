# VyaparAI Product Catalog System Documentation

## 📚 Complete Documentation Suite

This directory contains comprehensive documentation for the VyaparAI Product Catalog & Inventory Management System.

### 📖 Documentation Files

| Document | Description | Audience |
|----------|-------------|----------|
| **[PRODUCT_CATALOG_USER_MANUAL.md](./PRODUCT_CATALOG_USER_MANUAL.md)** | Complete user manual with detailed instructions | All Users |
| **[QUICK_REFERENCE_GUIDE.md](./QUICK_REFERENCE_GUIDE.md)** | Quick reference for common operations | All Users |
| **[API_TESTING_GUIDE.md](./API_TESTING_GUIDE.md)** | Comprehensive API testing examples | Developers |
| **[SYSTEM_ARCHITECTURE_GUIDE.md](./SYSTEM_ARCHITECTURE_GUIDE.md)** | System architecture and technical details | Technical Teams |
| **[CSV_TEMPLATE_EXAMPLE.csv](./CSV_TEMPLATE_EXAMPLE.csv)** | CSV template with example data | Store Owners |

---

## 🚀 Quick Start

### For Store Owners
1. **Read**: [Quick Reference Guide](./QUICK_REFERENCE_GUIDE.md) for immediate help
2. **Download**: [CSV Template](./CSV_TEMPLATE_EXAMPLE.csv) for bulk uploads
3. **Learn**: [User Manual](./PRODUCT_CATALOG_USER_MANUAL.md) for detailed instructions

### For Administrators
1. **Review**: [User Manual - Admin Section](./PRODUCT_CATALOG_USER_MANUAL.md#admin-user-guide)
2. **Test**: [API Testing Guide](./API_TESTING_GUIDE.md) for endpoint validation
3. **Understand**: [System Architecture](./SYSTEM_ARCHITECTURE_GUIDE.md) for technical details

### For Developers
1. **Study**: [System Architecture Guide](./SYSTEM_ARCHITECTURE_GUIDE.md)
2. **Test**: [API Testing Guide](./API_TESTING_GUIDE.md)
3. **Reference**: [User Manual](./PRODUCT_CATALOG_USER_MANUAL.md) for business logic

---

## 🎯 System Overview

The VyaparAI Product Catalog System is a **shared inventory management platform** that provides:

### ✨ Key Features
- **🌍 Global Product Catalog**: Centralized product database with deduplication
- **🏪 Store-Specific Inventory**: Individual store inventory management
- **🗣️ Regional Language Support**: Multi-language product names
- **✅ Quality Control**: Admin approval workflow for product quality
- **📊 Bulk Operations**: CSV uploads and bulk management tools
- **🔍 Smart Matching**: Find existing products before creating new ones

### 🏗️ Architecture
- **Backend**: AWS Lambda + FastAPI (Python)
- **Database**: DynamoDB (NoSQL)
- **Storage**: S3 (Files & Images)
- **Frontend**: React PWA
- **Authentication**: JWT-based with role permissions

---

## 👥 User Roles

### 🔧 Admin Users
- **Full System Access**: All endpoints and operations
- **Product Approval**: Verify, flag, or reject products
- **Bulk Operations**: Import/export large datasets
- **Analytics Access**: System-wide analytics and reporting
- **Quality Management**: Set quality standards and manage product status

### 🏪 Store Owners
- **Store Inventory Management**: Manage their store's inventory
- **Product Creation**: Add new products to global catalog (pending approval)
- **Regional Names**: Contribute regional language names
- **CSV Uploads**: Bulk upload inventory via CSV
- **Limited Analytics**: Store-specific analytics only

---

## 🔗 API Endpoints

### Base URL
```
https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws
```

### Authentication
All API calls require a JWT token:
```
Authorization: Bearer {your_jwt_token}
```

### Key Endpoints

#### Admin Endpoints
- `GET /api/v1/admin/products/statuses` - Get product statuses
- `GET /api/v1/admin/products/needing-review` - Products needing review
- `PUT /api/v1/admin/products/{id}/status` - Update product status
- `POST /api/v1/admin/import/common-indian-products` - Import products
- `GET /api/v1/admin/analytics/product-quality` - Quality analytics

#### Store Owner Endpoints
- `GET /api/v1/inventory/products` - Get store inventory
- `POST /api/v1/inventory/products` - Add product to inventory
- `POST /api/v1/inventory/products/match` - Find existing products
- `POST /api/v1/inventory/bulk-upload/csv` - Upload CSV
- `GET /api/v1/inventory/bulk-upload/jobs/{id}/status` - Check upload status

---

## 📊 Current System Status

### ✅ Production Ready Features
- **Product Catalog**: 16 high-quality products seeded
- **Quality Control**: Admin approval workflow active
- **Bulk Upload**: CSV processing with deduplication
- **Regional Support**: Multi-language product names
- **Analytics**: Comprehensive monitoring and reporting
- **Cleanup System**: Safe data cleanup with backups

### 📈 System Metrics
- **Total Products**: 16 verified and admin-created products
- **Verification Rate**: 31.2% (5/16 products verified)
- **Status Distribution**: 5 verified, 11 admin_created
- **Regional Coverage**: Multi-language support included
- **Quality Standards**: All products meet high-quality criteria

---

## 🛠️ Common Operations

### For Store Owners

#### Add Product to Inventory
```bash
curl -X POST "https://your-api-url/api/v1/inventory/products" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Basmati Rice 1kg",
    "brand": "India Gate",
    "category": "Rice & Grains",
    "barcode": "8901030875391",
    "quantity": 50,
    "cost_price": "120.00",
    "selling_price": "150.00"
  }'
```

#### Upload CSV Inventory
```bash
curl -X POST "https://your-api-url/api/v1/inventory/bulk-upload/csv" \
  -H "Authorization: Bearer {store_token}" \
  -F "file=@inventory.csv"
```

### For Administrators

#### Approve Product
```bash
curl -X PUT "https://your-api-url/api/v1/admin/products/{product_id}/status" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "verified",
    "notes": "High quality product"
  }'
```

#### Import Common Products
```bash
curl -X POST "https://your-api-url/api/v1/admin/import/common-indian-products" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## 🚨 Important Notes

### ⚠️ Data Types
- **Prices**: Always send as strings (`"120.00"`) not floats (`120.0`)
- **Barcodes**: Must be valid format (8, 12, 13, or 14 digits)
- **Quantities**: Use integers for stock quantities

### 🔐 Security
- **JWT Tokens**: Keep secure and don't share
- **Role Permissions**: Respect admin vs store owner access
- **Data Validation**: Always validate input data

### 📋 Best Practices
- **Check Existing First**: Always search before adding new products
- **Use Regional Names**: Contribute local language names
- **Quality Data**: Provide complete and accurate information
- **Regular Updates**: Keep inventory data current

---

## 🆘 Support & Troubleshooting

### Common Issues
1. **"Admin access required"** - Check JWT token role
2. **"Float types not supported"** - Send prices as strings
3. **CSV Upload Fails** - Check format and required fields
4. **Product Not Visible** - Verify store_id and product status

### Getting Help
1. **Check Documentation**: Review relevant manual sections
2. **Test API**: Use testing guide for validation
3. **Contact Admin**: Reach out to system administrators
4. **Report Issues**: Document problems with full details

---

## 📞 Contact Information

- **System Admin**: admin@vyapaarai.com
- **Technical Support**: support@vyapaarai.com
- **Documentation**: docs@vyapaarai.com

---

## 📝 Version History

- **v1.0.0** - Initial system deployment with core features
- **v1.1.0** - Added regional language support
- **v1.2.0** - Implemented quality control workflow
- **v1.3.0** - Added bulk import capabilities
- **v1.4.0** - Production seeding and cleanup system

---

*This documentation is regularly updated. Please check for the latest version and provide feedback for improvements.*



