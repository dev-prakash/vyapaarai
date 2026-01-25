# Changelog

All notable changes to VyapaarAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Dynamic GST Reference Tables** - Admin can now update GST rates without code deployment
  - New DynamoDB tables: `vyaparai-gst-rates-{env}` and `vyaparai-hsn-mappings-{env}`
  - Repository layer (`gst_repository.py`) for CRUD operations with audit logging
  - In-memory caching layer (`gst_cache.py`) with 5-minute TTL for performance
  - Dynamic GST service (`dynamic_gst_service.py`) with DB lookup and static fallback
  - Admin API endpoints for GST management:
    - `GET /admin/gst/categories` - List all GST categories
    - `POST /admin/gst/categories` - Create new category
    - `PUT /admin/gst/categories/{code}` - Update category (including rate changes)
    - `DELETE /admin/gst/categories/{code}` - Soft delete category
    - `GET /admin/gst/hsn` - List HSN mappings
    - `POST /admin/gst/hsn` - Create HSN mapping
    - `PUT /admin/gst/hsn/{code}` - Update HSN mapping
    - `DELETE /admin/gst/hsn/{code}` - Soft delete HSN mapping
    - `POST /admin/gst/cache/refresh` - Force cache refresh
    - `POST /admin/gst/seed` - Seed tables from static config
    - `GET /admin/gst/cache/stats` - View cache statistics
  - Seeding script (`scripts/seed_gst_tables.py`) to migrate from static config
  - Local test script (`scripts/test_gst_local.py`) for manual GST verification
  - Comprehensive unit tests (21 tests) with regression markers

- **GST Integration in Global Catalog** - Products are now classified with GST when added to catalog
  - Auto-suggest GST category from product name during promotion approval
  - Admin can assign HSN code, GST rate, cess rate when approving products
  - GST fields inherited by store inventory on promotion
  - New admin endpoints for GST management:
    - `GET /admin/products/gst/categories` - List all GST categories
    - `GET /admin/products/gst/suggest/{name}` - Get GST suggestion for product
    - `PUT /admin/products/global/{id}/gst` - Update product GST classification
    - `GET /admin/products/global/without-gst` - Find products needing GST assignment

### Changed
- GST service now uses dynamic rate lookup with database-first, static fallback strategy
- `get_all_gst_categories()`, `get_hsn_info()`, `suggest_gst_category()` are now async methods
- GST rate priority: store override > product rate > dynamic HSN lookup > static fallback > default 18%

---

## [0.2.0] - 2026-01-24

**GST Calculation System Release** - India-compliant multi-slab GST

### Added
- **Complete GST Calculation System** - India-compliant multi-slab GST with CGST/SGST breakdown
  - 5 GST rate slabs: 0%, 5%, 12%, 18%, 28% with optional cess
  - 55+ GST categories covering all kirana/retail items
  - 80+ HSN code mappings for automatic rate lookup
  - CGST/SGST split for intra-state, IGST for inter-state transactions
  - Rate-wise summary for GST filing compliance
  - Store-level GST rate overrides
  - Automatic category suggestion from product names
- GST API endpoints (`/api/v1/gst/*`) for categories, HSN lookup, and calculations
- GST fields in product operations (HSN code, GST rate, cess rate, exempt flag)
- GST test fixtures and 40+ unit tests with regression markers
- Regression tests for store registration address fields (E2E with Playwright)

### Changed
- **Cart API**: Now uses GST service for accurate tax calculation (replaces hardcoded 5%)
- **Orders API**: Now uses GST service with full CGST/SGST breakdown (replaces hardcoded 5%)
- Store registration: State dropdown now appears before City (consistent with customer registration)
- Store registration: City field now uses Autocomplete filtered by selected state
- Store registration: Delivery radius max increased from 20km to 100km

### Fixed
- Store registration: Address form field order (State now before City)
- Store registration: City dropdown now filtered by selected state (uses indianLocations.ts)
- Store registration: Delivery radius validation (1-100 km range)
- Store registration: Improved error handling with specific error messages

---

## [0.1.0] - 2026-01-24

**First Official Release** - VyapaarAI Initial Production Release

### Added
- Initial VyapaarAI platform
- Store registration and management
- Digital Khata (credit management) system
- Customer authentication with OTP
- Product and inventory management
- Order processing system with stock validation
- Gupshup SMS integration for OTP delivery
- Automated development workflows (Bug, Feature, Refactor, Hotfix triggers)
- Auto-test analysis script for intelligent test generation
- Comprehensive test suite for stores API (54 tests)
- DevOps infrastructure (branching strategy, CI/CD scripts)
- Unified deployment system with `/deploy` command
- AWS deployment analysis documentation

### Infrastructure
- AWS Lambda deployment (`vyaparai-api-prod`)
- DynamoDB tables for all data storage
- S3 + CloudFront for frontend hosting
- API Gateway for REST endpoints

### Security
- OTP hidden in production for customer auth endpoint
- IAM roles with least-privilege permissions

### Documentation
- CLAUDE.md with workflow triggers and slash commands
- WORKFLOWS.md with automated development workflows
- AWS_DEPLOYMENT_ANALYSIS.md with infrastructure documentation
