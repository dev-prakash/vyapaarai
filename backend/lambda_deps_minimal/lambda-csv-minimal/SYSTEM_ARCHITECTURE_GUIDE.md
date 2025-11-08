# VyaparAI Product Catalog System Architecture Guide

## System Overview

The VyaparAI Product Catalog System is a serverless, cloud-native inventory management platform built on AWS services. It provides a shared product catalog with store-specific inventory management, regional language support, and quality control workflows.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React PWA)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Store     │  │   Admin     │  │   Mobile    │            │
│  │  Dashboard  │  │  Dashboard  │  │   Scanner   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTPS/API Calls
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AWS Lambda Function                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              FastAPI Application                        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │   Admin     │  │   Store     │  │   Import    │     │   │
│  │  │  Endpoints  │  │  Endpoints  │  │  Pipeline   │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  DynamoDB   │ │     S3      │ │  External   │
│   Tables    │ │   Storage   │ │    APIs     │
│             │ │             │ │             │
│ ┌─────────┐ │ │ ┌─────────┐ │ │ ┌─────────┐ │
│ │ Global  │ │ │ │  CSV    │ │ │ │  Open   │ │
│ │Products │ │ │ │ Files   │ │ │ │  Food   │ │
│ └─────────┘ │ │ └─────────┘ │ │ │  Facts  │ │
│             │ │             │ │ └─────────┘ │
│ ┌─────────┐ │ │ ┌─────────┐ │ │             │
│ │ Store   │ │ │ │Product  │ │ │             │
│ │Inventory│ │ │ │ Images  │ │ │             │
│ └─────────┘ │ │ └─────────┘ │ │             │
│             │ │             │ │             │
│ ┌─────────┐ │ │ ┌─────────┐ │ │             │
│ │  CSV    │ │ │ │Backups  │ │ │             │
│ │  Jobs   │ │ │ │         │ │ │             │
│ └─────────┘ │ │ └─────────┘ │ │             │
└─────────────┘ └─────────────┘ └─────────────┘
```

## Core Components

### 1. Frontend (React PWA)
- **Technology**: React with TypeScript
- **Deployment**: AWS S3 + CloudFront
- **Features**: 
  - Store inventory management
  - Admin dashboard
  - Mobile barcode scanning
  - Regional language support

### 2. Backend (AWS Lambda)
- **Technology**: Python 3.11 + FastAPI
- **Runtime**: AWS Lambda
- **Features**:
  - RESTful API endpoints
  - JWT authentication
  - Role-based access control
  - Async processing

### 3. Database (DynamoDB)
- **Global Products Table**: Master product catalog
- **Store Inventory Table**: Store-specific inventory
- **CSV Jobs Table**: Bulk upload job tracking
- **Features**:
  - NoSQL document storage
  - Global Secondary Indexes (GSIs)
  - Auto-scaling
  - Point-in-time recovery

### 4. Storage (S3)
- **CSV Files**: Bulk upload temporary storage
- **Product Images**: Content-addressed storage
- **Backups**: Automated system backups
- **Features**:
  - Versioning enabled
  - Lifecycle policies
  - Cross-region replication

### 5. External Integrations
- **Open Food Facts API**: Product data import
- **Regional Language APIs**: Translation services
- **Image Processing**: Content hashing and optimization

## Data Flow

### 1. Product Creation Flow
```
Store Owner → API → Lambda → DynamoDB (Global Products)
                    ↓
              Quality Check → Admin Review → Approval
                    ↓
              DynamoDB (Store Inventory)
```

### 2. Bulk Upload Flow
```
CSV Upload → S3 → Lambda Processing → DynamoDB
     ↓
Job Tracking → Status Updates → Completion Notification
```

### 3. Product Matching Flow
```
Product Search → Fuzzy Matching → Existing Product Found
     ↓
Add to Store Inventory (No Global Product Creation)
```

## Database Schema

### Global Products Table
```json
{
  "product_id": "string (PK)",
  "name": "string",
  "brand": "string", 
  "category": "string",
  "barcode": "string (GSI)",
  "image_hash": "string (GSI)",
  "canonical_image_urls": {
    "original": "string",
    "thumbnail": "string",
    "medium": "string"
  },
  "regional_names": {
    "IN-MH": ["string"],
    "IN-TN": ["string"]
  },
  "attributes": {
    "weight": "string",
    "description": "string"
  },
  "verification_status": "string",
  "quality_score": "number",
  "created_at": "string",
  "updated_at": "string"
}
```

### Store Inventory Table
```json
{
  "store_id": "string (PK)",
  "product_id": "string (SK)",
  "quantity": "number",
  "cost_price": "decimal",
  "selling_price": "decimal",
  "reorder_level": "number",
  "supplier": "string",
  "location": "string",
  "custom_image_urls": {
    "original": "string"
  },
  "notes": "string",
  "last_updated": "string"
}
```

### CSV Jobs Table
```json
{
  "jobId": "string (PK)",
  "store_id": "string",
  "status": "string",
  "total_rows": "number",
  "processed": "number",
  "successful": "number",
  "failed": "number",
  "duplicates_found": "number",
  "createdAt": "string",
  "completedAt": "string"
}
```

## Security Architecture

### 1. Authentication
- **JWT Tokens**: Stateless authentication
- **Role-Based Access**: Admin vs Store Owner permissions
- **Token Expiration**: 30-day token lifetime
- **Secure Storage**: HTTPS-only communication

### 2. Authorization
- **Admin Endpoints**: Require admin role
- **Store Endpoints**: Require store_owner role
- **Resource Isolation**: Store owners can only access their data
- **API Rate Limiting**: Prevent abuse

### 3. Data Protection
- **Encryption at Rest**: DynamoDB encryption
- **Encryption in Transit**: HTTPS/TLS
- **Access Logging**: CloudTrail integration
- **Backup Security**: Encrypted backups

## Scalability & Performance

### 1. Auto-Scaling
- **Lambda**: Automatic scaling based on requests
- **DynamoDB**: On-demand capacity with auto-scaling
- **S3**: Unlimited storage capacity
- **CloudFront**: Global CDN for static assets

### 2. Performance Optimization
- **Connection Pooling**: Reuse database connections
- **Caching**: CloudFront edge caching
- **Batch Operations**: Efficient bulk processing
- **Async Processing**: Non-blocking operations

### 3. Monitoring
- **CloudWatch**: Application metrics and logs
- **X-Ray**: Distributed tracing
- **Custom Metrics**: Business-specific monitoring
- **Alerting**: Automated notifications

## Deployment Architecture

### 1. Infrastructure as Code
- **Terraform**: Infrastructure provisioning
- **AWS CDK**: Application deployment
- **GitHub Actions**: CI/CD pipeline
- **Environment Management**: Dev/Staging/Prod

### 2. Deployment Pipeline
```
Code Commit → GitHub Actions → Build → Test → Deploy
     ↓
Lambda Update → S3 Upload → CloudFront Invalidation
     ↓
Health Check → Monitoring → Alerting
```

### 3. Environment Configuration
- **Development**: Local development environment
- **Staging**: Pre-production testing
- **Production**: Live system with monitoring

## Disaster Recovery

### 1. Backup Strategy
- **DynamoDB**: Point-in-time recovery
- **S3**: Cross-region replication
- **Lambda**: Code versioning
- **Configuration**: Infrastructure as code

### 2. Recovery Procedures
- **RTO**: 4 hours (Recovery Time Objective)
- **RPO**: 1 hour (Recovery Point Objective)
- **Failover**: Multi-region deployment
- **Testing**: Regular disaster recovery drills

## Cost Optimization

### 1. Serverless Benefits
- **Pay-per-use**: Lambda pricing model
- **No idle costs**: DynamoDB on-demand
- **Auto-scaling**: No over-provisioning
- **Managed services**: Reduced operational overhead

### 2. Cost Monitoring
- **AWS Cost Explorer**: Detailed cost analysis
- **Budget Alerts**: Automated cost notifications
- **Resource Tagging**: Cost allocation
- **Optimization Recommendations**: AWS Trusted Advisor

## Monitoring & Observability

### 1. Application Monitoring
- **CloudWatch Logs**: Centralized logging
- **CloudWatch Metrics**: Performance monitoring
- **X-Ray Tracing**: Request tracing
- **Custom Dashboards**: Business metrics

### 2. Infrastructure Monitoring
- **AWS Health**: Service health status
- **CloudWatch Alarms**: Automated alerting
- **SNS Notifications**: Alert delivery
- **PagerDuty Integration**: Incident management

## API Design Principles

### 1. RESTful Design
- **Resource-based URLs**: Clear endpoint structure
- **HTTP Methods**: Proper verb usage
- **Status Codes**: Meaningful response codes
- **JSON Format**: Consistent data format

### 2. Error Handling
- **Standardized Errors**: Consistent error format
- **Error Codes**: Machine-readable error codes
- **Error Messages**: Human-readable descriptions
- **Error Logging**: Comprehensive error tracking

### 3. Versioning
- **API Versioning**: URL-based versioning
- **Backward Compatibility**: Maintain compatibility
- **Deprecation Policy**: Clear deprecation timeline
- **Migration Guide**: Upgrade instructions

## Development Workflow

### 1. Local Development
- **Docker**: Containerized development
- **LocalStack**: Local AWS services
- **Hot Reload**: Fast development cycle
- **Testing**: Unit and integration tests

### 2. Code Quality
- **Linting**: Code style enforcement
- **Type Checking**: TypeScript/Python type checking
- **Testing**: Automated test suite
- **Code Review**: Peer review process

### 3. Deployment
- **Feature Branches**: Isolated development
- **Pull Requests**: Code review process
- **Automated Testing**: CI/CD pipeline
- **Staged Deployment**: Gradual rollout

## Maintenance & Updates

### 1. Regular Maintenance
- **Security Updates**: Regular patching
- **Dependency Updates**: Keep dependencies current
- **Performance Tuning**: Optimize based on metrics
- **Capacity Planning**: Proactive scaling

### 2. System Updates
- **Blue-Green Deployment**: Zero-downtime updates
- **Rollback Procedures**: Quick rollback capability
- **Health Checks**: Automated validation
- **Monitoring**: Post-deployment monitoring

This architecture provides a robust, scalable, and maintainable foundation for the VyaparAI Product Catalog System.



