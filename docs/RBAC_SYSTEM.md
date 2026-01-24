# VyaparAI Role-Based Access Control (RBAC) System

## Document Information
- **Last Updated**: December 3, 2025
- **Version**: 2.0.0
- **Status**: Architecture Complete, API Implementation Pending
- **Related Docs**:
  - [RBAC_ARCHITECTURE.md](/docs/RBAC_ARCHITECTURE.md) - Original design doc
  - [DATABASE_SCHEMA_DOCUMENTATION.md](/backend/database/DATABASE_SCHEMA_DOCUMENTATION.md) - Table schemas

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Database Tables](#database-tables)
4. [Permissions System](#permissions-system)
5. [Roles System](#roles-system)
6. [Permission Evaluation](#permission-evaluation)
7. [API Endpoints](#api-endpoints)
8. [Frontend Integration](#frontend-integration)
9. [Admin Workflows](#admin-workflows)
10. [Security & Best Practices](#security--best-practices)
11. [Migration Strategy](#migration-strategy)
12. [Troubleshooting](#troubleshooting)

---

## Overview

### What is RBAC?

**Role-Based Access Control (RBAC)** is a security model that restricts system access based on user roles and permissions. VyaparAI's RBAC system provides granular control over who can perform what actions.

### Key Features

- **Granular Permissions**: 22 fine-grained permissions across 5 categories
- **Role Hierarchy**: 5 default roles with clear privilege levels
- **Flexible Assignment**: Direct permissions + role-based permissions
- **Permission Overrides**: Deny specific permissions to role members
- **Audit Trail**: Complete history of permission assignments
- **Temporal Permissions**: Time-limited access grants
- **Super Admin Protection**: Prevents accidental privilege loss

### Use Cases

1. **Store Management**: Grant store managers access to inventory but not user management
2. **Catalog Editors**: Allow product CRUD without analytics access
3. **Read-Only Viewers**: Provide dashboard access without modification rights
4. **Temporary Access**: Grant time-limited permissions for contractors
5. **Compliance**: Audit who has access to what resources

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      USER REQUEST                           │
│         (e.g., POST /api/v1/products/create)               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 AUTHENTICATION LAYER                         │
│              (Verify JWT Token)                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              PERMISSION EVALUATION ENGINE                    │
│                                                             │
│  1. Check if Super Admin (bypass)                          │
│  2. Load user's roles from DynamoDB                        │
│  3. Collect permissions from all roles                     │
│  4. Add direct permissions                                 │
│  5. Apply permission overrides (deny takes precedence)     │
│  6. Check if required permission exists                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
                  ┌────┴────┐
                  │ ALLOW?  │
                  └────┬────┘
                       │
            ┌──────────┴──────────┐
            │                     │
        ✅ YES                 ❌ NO
            │                     │
            ▼                     ▼
    Execute Action       Return 403 Forbidden
```

### Design Principles

1. **Principle of Least Privilege**: Grant minimum permissions needed
2. **Deny by Default**: No permission = no access
3. **Explicit Deny Wins**: Overrides always deny (never grant)
4. **Hierarchical Roles**: Lower level numbers = higher privileges
5. **Immutable Audit**: Permission assignments are logged permanently

---

## Database Tables

### 1. vyaparai-permissions-prod

**Purpose**: Master list of all system permissions

**Schema**:
```typescript
interface Permission {
  permission_id: string;          // PK: "PERM_PRODUCT_CREATE"
  name: string;                   // "Create Products"
  description: string;            // Detailed explanation
  category: string;               // "product_management" | "user_management" | ...
  resource: string;               // "products" | "users" | "roles"
  action: string;                 // "create" | "read" | "update" | "delete"
  status: "active" | "deprecated";
  created_at: string;             // ISO timestamp
  updated_at: string;             // ISO timestamp
}
```

**Global Secondary Index (GSI)**:
- **CategoryIndex**: Query permissions by category
  - PK: `category`
  - SK: `status`

**Seeded Permissions** (22 total):

| Category | Permissions |
|----------|-------------|
| **Product Management** (6) | CREATE, READ, UPDATE, DELETE, EXPORT, IMPORT_BULK |
| **User Management** (6) | CREATE, READ, UPDATE, DELETE, ASSIGN_ROLES, ASSIGN_PERMISSIONS |
| **Role Management** (4) | CREATE, READ, UPDATE, DELETE |
| **Analytics** (3) | VIEW, REPORTS_GENERATE, REPORTS_EXPORT |
| **Settings** (3) | VIEW, UPDATE, SYSTEM_CONFIG |

**Example Query**:
```python
# Get all active product management permissions
dynamodb.query(
    TableName='vyaparai-permissions-prod',
    IndexName='CategoryIndex',
    KeyConditionExpression='category = :cat AND #status = :status',
    ExpressionAttributeNames={'#status': 'status'},
    ExpressionAttributeValues={
        ':cat': 'product_management',
        ':status': 'active'
    }
)
```

---

### 2. vyaparai-roles-prod

**Purpose**: Role definitions with permission bundles

**Schema**:
```typescript
interface Role {
  role_id: string;                // PK: "ROLE_SUPER_ADMIN"
  role_name: string;              // "Super Administrator"
  description: string;            // Role explanation
  permissions: string[];          // ["*"] or ["PERM_ID1", "PERM_ID2"]
  hierarchy_level: number;        // 1-100 (lower = more privileged)
  is_system_role: boolean;        // System roles can't be deleted
  status: "active" | "inactive";
  created_at: string;
  updated_at: string;
}
```

**Global Secondary Index (GSI)**:
- **HierarchyIndex**: Query roles by privilege level
  - PK: `status`
  - SK: `hierarchy_level`

**Seeded Roles**:

| Role | Level | Permissions | Description |
|------|-------|-------------|-------------|
| **ROLE_SUPER_ADMIN** | 1 | ["*"] (all) | Full system access, can assign any role |
| **ROLE_ADMIN** | 10 | Product (all), User (view/update), Analytics, Settings (view) | Department heads, senior managers |
| **ROLE_STORE_MANAGER** | 20 | Product (read/update/export), Analytics (view), Reports (generate) | Store-level managers |
| **ROLE_CATALOG_EDITOR** | 30 | Product (CRUD + export) | Catalog management specialists |
| **ROLE_VIEWER** | 50 | Product (read), Analytics (view) | Read-only access for stakeholders |

**Example Query**:
```python
# Get all active roles sorted by privilege (highest first)
dynamodb.query(
    TableName='vyaparai-roles-prod',
    IndexName='HierarchyIndex',
    KeyConditionExpression='#status = :status',
    ExpressionAttributeNames={'#status': 'status'},
    ExpressionAttributeValues={':status': 'active'},
    ScanIndexForward=True  # Ascending order (level 1 first)
)
```

---

### 3. vyaparai-user-permissions-prod

**Purpose**: Junction table tracking user-permission assignments

**Schema**:
```typescript
interface UserPermission {
  assignment_id: string;          // PK: "{user_id}#{permission_id}"
  user_id: string;                // User receiving permission
  permission_id: string;          // Permission granted
  granted_by: string;             // Admin who granted permission
  assignment_type: string;        // "direct" | "role_inherited" | "override"
  expires_at?: string;            // Optional expiration (ISO timestamp)
  assigned_at: string;            // ISO timestamp
}
```

**Global Secondary Indexes (GSIs)**:
- **UserPermissionsIndex**: Get all permissions for a user
  - PK: `user_id`
  - SK: `assignment_type`
- **PermissionUsersIndex**: Get all users with a permission
  - PK: `permission_id`

**Example Query**:
```python
# Get all direct permissions for a user
dynamodb.query(
    TableName='vyaparai-user-permissions-prod',
    IndexName='UserPermissionsIndex',
    KeyConditionExpression='user_id = :uid AND assignment_type = :type',
    ExpressionAttributeValues={
        ':uid': 'user_johndoe@example.com',
        ':type': 'direct'
    }
)
```

---

## Permissions System

### Permission Naming Convention

**Format**: `PERM_{RESOURCE}_{ACTION}`

**Examples**:
- `PERM_PRODUCT_CREATE` - Create new products
- `PERM_USER_UPDATE` - Update user profiles
- `PERM_ROLE_DELETE` - Delete custom roles
- `PERM_ANALYTICS_VIEW` - View analytics dashboard
- `PERM_REPORTS_EXPORT` - Export reports to CSV/PDF

### Permission Categories

#### 1. Product Management (product_management)
- `PERM_PRODUCT_CREATE` - Create new products in catalog
- `PERM_PRODUCT_READ` - View product details
- `PERM_PRODUCT_UPDATE` - Edit existing products
- `PERM_PRODUCT_DELETE` - Remove products from catalog
- `PERM_PRODUCT_EXPORT` - Export product data to CSV
- `PERM_PRODUCT_IMPORT_BULK` - Bulk import via CSV

#### 2. User Management (user_management)
- `PERM_USER_CREATE` - Create new user accounts
- `PERM_USER_READ` - View user profiles
- `PERM_USER_UPDATE` - Edit user details
- `PERM_USER_DELETE` - Deactivate user accounts
- `PERM_USER_ASSIGN_ROLES` - Assign roles to users
- `PERM_USER_ASSIGN_PERMISSIONS` - Grant direct permissions

#### 3. Role Management (role_management)
- `PERM_ROLE_CREATE` - Define new custom roles
- `PERM_ROLE_READ` - View role definitions
- `PERM_ROLE_UPDATE` - Modify role permissions
- `PERM_ROLE_DELETE` - Remove custom roles

#### 4. Analytics (analytics)
- `PERM_ANALYTICS_VIEW` - Access analytics dashboards
- `PERM_REPORTS_GENERATE` - Generate custom reports
- `PERM_REPORTS_EXPORT` - Export reports to files

#### 5. Settings (settings)
- `PERM_SETTINGS_VIEW` - View system settings
- `PERM_SETTINGS_UPDATE` - Modify app settings
- `PERM_SETTINGS_SYSTEM_CONFIG` - Change critical configs

### Adding New Permissions

**Step 1: Define Permission**
```python
# Add to seed data or create via API
new_permission = {
    "permission_id": "PERM_INVENTORY_ADJUST",
    "name": "Adjust Inventory",
    "description": "Manually adjust stock levels for inventory corrections",
    "category": "product_management",
    "resource": "inventory",
    "action": "adjust",
    "status": "active",
    "created_at": datetime.utcnow().isoformat(),
    "updated_at": datetime.utcnow().isoformat()
}

permissions_table.put_item(Item=new_permission)
```

**Step 2: Update Backend Checks**
```python
# In inventory adjustment endpoint
@router.post("/inventory/adjust")
async def adjust_inventory(user=Depends(get_current_user)):
    if not check_permission(user.id, "PERM_INVENTORY_ADJUST"):
        raise HTTPException(403, "Insufficient permissions")

    # Perform adjustment
    ...
```

**Step 3: Update Frontend**
```typescript
// Conditionally render button
<PermissionGuard permission="PERM_INVENTORY_ADJUST">
  <Button onClick={adjustInventory}>Adjust Stock</Button>
</PermissionGuard>
```

**Step 4: Assign to Roles**
```python
# Add to appropriate roles
update_role("ROLE_STORE_MANAGER", add_permissions=["PERM_INVENTORY_ADJUST"])
```

---

## Roles System

### Role Hierarchy

**Hierarchy Levels** (1-100):
- **1-9**: Super Admin tier
- **10-19**: Admin tier
- **20-29**: Manager tier
- **30-49**: Editor/Contributor tier
- **50-99**: Viewer/Guest tier

**Hierarchy Rules**:
1. Users can only assign roles **at their level or lower**
2. Users cannot modify roles **at their level or higher**
3. System roles (is_system_role: true) **cannot be deleted**
4. Super Admin (level 1) bypasses all permission checks

### Default Roles

#### ROLE_SUPER_ADMIN (Level 1)
**Permissions**: `["*"]` (wildcard = all permissions)
**Use Case**: System administrators, platform owners
**Capabilities**:
- Full access to all features
- Can assign any role
- Can create/modify all roles
- Cannot be removed from system

**Assignment**:
```python
assign_role_to_user(
    user_id="admin@vyapaarai.com",
    role_id="ROLE_SUPER_ADMIN",
    granted_by="system"
)
```

#### ROLE_ADMIN (Level 10)
**Permissions**:
```python
[
    "PERM_PRODUCT_CREATE", "PERM_PRODUCT_READ", "PERM_PRODUCT_UPDATE",
    "PERM_PRODUCT_DELETE", "PERM_PRODUCT_EXPORT", "PERM_PRODUCT_IMPORT_BULK",
    "PERM_USER_READ", "PERM_USER_UPDATE",
    "PERM_ANALYTICS_VIEW", "PERM_REPORTS_GENERATE", "PERM_REPORTS_EXPORT",
    "PERM_SETTINGS_VIEW"
]
```
**Use Case**: Department heads, senior managers
**Limitations**: Cannot manage users or modify system settings

#### ROLE_STORE_MANAGER (Level 20)
**Permissions**:
```python
[
    "PERM_PRODUCT_READ", "PERM_PRODUCT_UPDATE", "PERM_PRODUCT_EXPORT",
    "PERM_ANALYTICS_VIEW", "PERM_REPORTS_GENERATE"
]
```
**Use Case**: Store-level managers, inventory supervisors
**Limitations**: Cannot create/delete products or access user management

#### ROLE_CATALOG_EDITOR (Level 30)
**Permissions**:
```python
[
    "PERM_PRODUCT_CREATE", "PERM_PRODUCT_READ", "PERM_PRODUCT_UPDATE",
    "PERM_PRODUCT_DELETE", "PERM_PRODUCT_EXPORT"
]
```
**Use Case**: Catalog management specialists
**Limitations**: No analytics or admin features

#### ROLE_VIEWER (Level 50)
**Permissions**:
```python
[
    "PERM_PRODUCT_READ",
    "PERM_ANALYTICS_VIEW"
]
```
**Use Case**: Read-only stakeholders, auditors, external partners
**Limitations**: Cannot modify any data

### Creating Custom Roles

```python
def create_custom_role(name, description, permissions, hierarchy_level):
    """Create a new custom role"""

    # Validate hierarchy (must be >= 30 for custom roles)
    if hierarchy_level < 30:
        raise ValueError("Custom roles must be level 30 or higher")

    role_id = f"ROLE_{name.upper().replace(' ', '_')}"

    role = {
        "role_id": role_id,
        "role_name": name,
        "description": description,
        "permissions": permissions,
        "hierarchy_level": hierarchy_level,
        "is_system_role": False,
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    roles_table.put_item(Item=role)
    return role

# Example: Create "Marketing Manager" role
marketing_role = create_custom_role(
    name="Marketing Manager",
    description="Manage marketing campaigns and analytics",
    permissions=[
        "PERM_PRODUCT_READ",
        "PERM_ANALYTICS_VIEW",
        "PERM_REPORTS_GENERATE",
        "PERM_REPORTS_EXPORT"
    ],
    hierarchy_level=35
)
```

---

## Permission Evaluation

### Evaluation Algorithm

```python
def evaluate_user_permissions(user_id: str) -> dict:
    """
    Evaluate all effective permissions for a user

    Returns:
        {
            "has_full_access": bool,
            "permissions": List[str]
        }
    """

    # Step 1: Check if super admin (bypass all checks)
    user = get_user_by_id(user_id)
    if user.get('role') == 'super_admin':
        return {
            "has_full_access": True,
            "permissions": ["*"]
        }

    # Step 2: Get user's assigned roles
    user_roles = user.get('assigned_roles', [])

    # Step 3: Collect permissions from all roles
    permissions_from_roles = set()
    for role_id in user_roles:
        role = get_role_by_id(role_id)
        if not role or role['status'] != 'active':
            continue

        # Check for wildcard
        if "*" in role['permissions']:
            return {
                "has_full_access": True,
                "permissions": ["*"]
            }

        # Add role permissions
        permissions_from_roles.update(role['permissions'])

    # Step 4: Get direct permissions
    direct_permissions = get_direct_permissions(user_id)

    # Step 5: Merge all permissions
    all_permissions = permissions_from_roles.union(direct_permissions)

    # Step 6: Apply permission overrides (deny takes precedence)
    overrides = user.get('permission_overrides', {})
    for permission, allowed in overrides.items():
        if not allowed:
            all_permissions.discard(permission)  # Remove denied permission
        else:
            all_permissions.add(permission)      # Add allowed permission

    # Step 7: Filter expired permissions
    all_permissions = filter_expired_permissions(user_id, all_permissions)

    return {
        "has_full_access": False,
        "permissions": list(all_permissions)
    }


def has_permission(user_id: str, permission_id: str) -> bool:
    """Check if user has a specific permission"""
    user_permissions = evaluate_user_permissions(user_id)

    # Check for full access
    if user_permissions['has_full_access']:
        return True

    # Check if permission exists
    return permission_id in user_permissions['permissions']
```

### Permission Check Flow

```
User Request
    │
    ▼
Super Admin?  ──YES──> ✅ ALLOW
    │
    NO
    ▼
Load User's Roles
    │
    ▼
Check for Wildcard ("*") in Roles  ──YES──> ✅ ALLOW
    │
    NO
    ▼
Collect Permissions from Roles
    │
    ▼
Add Direct Permissions
    │
    ▼
Apply Overrides (Deny wins)
    │
    ▼
Filter Expired Permissions
    │
    ▼
Required Permission in Set?  ──YES──> ✅ ALLOW
    │
    NO
    ▼
❌ DENY (403 Forbidden)
```

### Caching Strategy

To avoid querying DynamoDB on every request:

```python
import redis

redis_client = redis.Redis(host='localhost', port=6379)

def get_cached_user_permissions(user_id: str) -> dict:
    """Get permissions with caching (5 minute TTL)"""

    cache_key = f"user_permissions:{user_id}"

    # Check cache
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Evaluate and cache
    permissions = evaluate_user_permissions(user_id)
    redis_client.setex(
        cache_key,
        300,  # 5 minutes TTL
        json.dumps(permissions)
    )

    return permissions

def invalidate_user_permissions_cache(user_id: str):
    """Invalidate cache when permissions change"""
    redis_client.delete(f"user_permissions:{user_id}")
```

**Cache Invalidation Triggers**:
- Role assigned/removed
- Direct permission granted/revoked
- Role permissions modified
- Permission override added

---

## API Endpoints

### Permission Management

#### List All Permissions
```http
GET /api/v1/admin/permissions

Authorization: Bearer {super_admin_token}

Query Parameters:
- category (optional): Filter by category
- status (optional): active | deprecated

Response:
{
  "permissions": [
    {
      "permission_id": "PERM_PRODUCT_CREATE",
      "name": "Create Products",
      "description": "Create new products in catalog",
      "category": "product_management",
      "resource": "products",
      "action": "create",
      "status": "active"
    }
  ],
  "total": 22
}
```

#### Get Permission Details
```http
GET /api/v1/admin/permissions/{permission_id}

Authorization: Bearer {super_admin_token}

Response:
{
  "permission_id": "PERM_PRODUCT_CREATE",
  "name": "Create Products",
  "description": "Create new products in catalog",
  "category": "product_management",
  "resource": "products",
  "action": "create",
  "status": "active",
  "users_count": 15,  # Number of users with this permission
  "roles_count": 3    # Number of roles with this permission
}
```

#### Create Permission
```http
POST /api/v1/admin/permissions

Authorization: Bearer {super_admin_token}
Content-Type: application/json

Body:
{
  "permission_id": "PERM_INVENTORY_ADJUST",
  "name": "Adjust Inventory",
  "description": "Manually adjust stock levels",
  "category": "product_management",
  "resource": "inventory",
  "action": "adjust"
}

Response: 201 Created
{
  "permission_id": "PERM_INVENTORY_ADJUST",
  "status": "active",
  "created_at": "2025-12-03T10:30:00Z"
}
```

---

### Role Management

#### List All Roles
```http
GET /api/v1/admin/roles

Authorization: Bearer {admin_token}

Query Parameters:
- status (optional): active | inactive
- hierarchy_level_min (optional): Filter by min level
- hierarchy_level_max (optional): Filter by max level

Response:
{
  "roles": [
    {
      "role_id": "ROLE_SUPER_ADMIN",
      "role_name": "Super Administrator",
      "description": "Full system access",
      "permissions": ["*"],
      "hierarchy_level": 1,
      "is_system_role": true,
      "status": "active",
      "users_count": 2
    }
  ],
  "total": 5
}
```

#### Create Role
```http
POST /api/v1/admin/roles

Authorization: Bearer {admin_token}
Content-Type: application/json

Body:
{
  "role_name": "Marketing Manager",
  "description": "Manage marketing campaigns",
  "permissions": [
    "PERM_PRODUCT_READ",
    "PERM_ANALYTICS_VIEW",
    "PERM_REPORTS_GENERATE"
  ],
  "hierarchy_level": 35
}

Response: 201 Created
{
  "role_id": "ROLE_MARKETING_MANAGER",
  "status": "active",
  "created_at": "2025-12-03T10:30:00Z"
}
```

#### Update Role Permissions
```http
PUT /api/v1/admin/roles/{role_id}/permissions

Authorization: Bearer {admin_token}
Content-Type: application/json

Body:
{
  "permissions": [
    "PERM_PRODUCT_READ",
    "PERM_PRODUCT_UPDATE",
    "PERM_ANALYTICS_VIEW"
  ]
}

Response: 200 OK
{
  "role_id": "ROLE_MARKETING_MANAGER",
  "permissions_updated": 3,
  "updated_at": "2025-12-03T10:35:00Z"
}
```

---

### User Permission Management

#### Get User's Effective Permissions
```http
GET /api/v1/admin/users/{user_id}/permissions

Authorization: Bearer {admin_token}

Response:
{
  "user_id": "user_johndoe@example.com",
  "has_full_access": false,
  "permissions": [
    {
      "permission_id": "PERM_PRODUCT_READ",
      "source": "role",
      "role_id": "ROLE_CATALOG_EDITOR"
    },
    {
      "permission_id": "PERM_ANALYTICS_VIEW",
      "source": "direct",
      "granted_by": "admin@vyapaarai.com",
      "assigned_at": "2025-12-01T10:00:00Z",
      "expires_at": "2025-12-31T23:59:59Z"
    }
  ],
  "roles": [
    {
      "role_id": "ROLE_CATALOG_EDITOR",
      "role_name": "Catalog Editor",
      "assigned_at": "2025-11-15T10:00:00Z"
    }
  ]
}
```

#### Assign Role to User
```http
POST /api/v1/admin/users/{user_id}/roles

Authorization: Bearer {admin_token}
Content-Type: application/json

Body:
{
  "role_id": "ROLE_STORE_MANAGER"
}

Response: 201 Created
{
  "user_id": "user_johndoe@example.com",
  "role_id": "ROLE_STORE_MANAGER",
  "assigned_at": "2025-12-03T10:40:00Z"
}
```

#### Grant Direct Permission
```http
POST /api/v1/admin/users/{user_id}/permissions

Authorization: Bearer {admin_token}
Content-Type: application/json

Body:
{
  "permission_id": "PERM_REPORTS_EXPORT",
  "expires_at": "2025-12-31T23:59:59Z"  # Optional
}

Response: 201 Created
{
  "assignment_id": "user_johndoe@example.com#PERM_REPORTS_EXPORT",
  "assigned_at": "2025-12-03T10:45:00Z",
  "expires_at": "2025-12-31T23:59:59Z"
}
```

#### Revoke Permission
```http
DELETE /api/v1/admin/users/{user_id}/permissions/{permission_id}

Authorization: Bearer {admin_token}

Response: 200 OK
{
  "user_id": "user_johndoe@example.com",
  "permission_id": "PERM_REPORTS_EXPORT",
  "revoked_at": "2025-12-03T10:50:00Z"
}
```

---

## Frontend Integration

### React Context Provider

```typescript
// contexts/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';

interface AuthContextType {
  user: User | null;
  permissions: string[];
  hasPermission: (permission: string) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
  hasAllPermissions: (permissions: string[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);

  useEffect(() => {
    // Load user and permissions from API
    fetchUserPermissions().then(data => {
      setUser(data.user);
      setPermissions(data.permissions);
    });
  }, []);

  const hasPermission = (permission: string): boolean => {
    if (permissions.includes('*')) return true;
    return permissions.includes(permission);
  };

  const hasAnyPermission = (perms: string[]): boolean => {
    if (permissions.includes('*')) return true;
    return perms.some(p => permissions.includes(p));
  };

  const hasAllPermissions = (perms: string[]): boolean => {
    if (permissions.includes('*')) return true;
    return perms.every(p => permissions.includes(p));
  };

  return (
    <AuthContext.Provider value={{ user, permissions, hasPermission, hasAnyPermission, hasAllPermissions }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
```

### Permission Guard Component

```typescript
// components/PermissionGuard.tsx
interface PermissionGuardProps {
  permission: string | string[];
  requireAll?: boolean;  // For multiple permissions: AND vs OR
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const PermissionGuard: React.FC<PermissionGuardProps> = ({
  permission,
  requireAll = false,
  fallback = null,
  children
}) => {
  const { hasPermission, hasAnyPermission, hasAllPermissions } = useAuth();

  const hasAccess = useMemo(() => {
    if (typeof permission === 'string') {
      return hasPermission(permission);
    }

    return requireAll
      ? hasAllPermissions(permission)
      : hasAnyPermission(permission);
  }, [permission, requireAll]);

  if (!hasAccess) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
};

// Usage Examples
<PermissionGuard permission="PERM_PRODUCT_CREATE">
  <Button onClick={createProduct}>Create Product</Button>
</PermissionGuard>

<PermissionGuard
  permission={["PERM_PRODUCT_UPDATE", "PERM_PRODUCT_DELETE"]}
  requireAll={true}
>
  <Button onClick={bulkDelete}>Bulk Delete</Button>
</PermissionGuard>

<PermissionGuard
  permission="PERM_SETTINGS_UPDATE"
  fallback={<Alert severity="info">You don't have permission to edit settings</Alert>}
>
  <SettingsForm />
</PermissionGuard>
```

### Route Protection

```typescript
// routes/ProtectedRoute.tsx
import { Navigate } from 'react-router-dom';

interface ProtectedRouteProps {
  permission: string | string[];
  requireAll?: boolean;
  redirectTo?: string;
  children: React.ReactElement;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  permission,
  requireAll = false,
  redirectTo = '/unauthorized',
  children
}) => {
  const { hasPermission, hasAnyPermission, hasAllPermissions } = useAuth();

  const hasAccess = useMemo(() => {
    if (typeof permission === 'string') {
      return hasPermission(permission);
    }

    return requireAll
      ? hasAllPermissions(permission)
      : hasAnyPermission(permission);
  }, [permission, requireAll]);

  if (!hasAccess) {
    return <Navigate to={redirectTo} replace />;
  }

  return children;
};

// Usage in Router
<Route
  path="/admin/users"
  element={
    <ProtectedRoute permission="PERM_USER_READ">
      <UsersPage />
    </ProtectedRoute>
  }
/>
```

---

## Admin Workflows

### Workflow 1: Assign Role to New User

1. **Admin navigates to User Management**
   - URL: `/admin/users`
   - Required Permission: `PERM_USER_READ`

2. **Select user and click "Assign Role"**
   - Modal shows available roles
   - Roles filtered by hierarchy (can't assign higher-level roles)

3. **Choose role and confirm**
   - API: `POST /api/v1/admin/users/{user_id}/roles`
   - Response includes permission summary

4. **User receives notification**
   - Email: "You've been assigned the role of [Role Name]"
   - User must re-login to get new permissions

### Workflow 2: Grant Temporary Permission

1. **Admin needs to grant contractor access for 1 week**

2. **Navigate to user profile**
   - URL: `/admin/users/{user_id}`

3. **Click "Grant Direct Permission"**
   - Select permission: `PERM_REPORTS_EXPORT`
   - Set expiration: `2025-12-10T23:59:59Z`

4. **Confirm assignment**
   - API: `POST /api/v1/admin/users/{user_id}/permissions`
   - Permission auto-revokes after expiration

### Workflow 3: Create Custom Role

1. **Admin navigates to Role Management**
   - URL: `/admin/roles`
   - Required Permission: `PERM_ROLE_CREATE`

2. **Click "Create Role"**
   - Enter role name: "Marketing Manager"
   - Enter description
   - Select hierarchy level: 35 (Editor tier)

3. **Select permissions**
   - Check: `PERM_PRODUCT_READ`, `PERM_ANALYTICS_VIEW`, `PERM_REPORTS_GENERATE`

4. **Save and assign to users**
   - API: `POST /api/v1/admin/roles`
   - API: `POST /api/v1/admin/users/{user_id}/roles`

### Workflow 4: Audit User Permissions

1. **Admin needs to audit who can delete products**

2. **Navigate to Permission Details**
   - URL: `/admin/permissions/PERM_PRODUCT_DELETE`

3. **View users with this permission**
   - Shows users with direct assignment
   - Shows roles that include this permission
   - Shows users in those roles

4. **Export audit report**
   - CSV with columns: User ID, Name, Email, Source (direct/role), Assigned Date

---

## Security & Best Practices

### Security Best Practices

1. **Validate on Both Frontend and Backend**
   ```python
   # ALWAYS check permissions server-side
   @router.delete("/products/{product_id}")
   async def delete_product(product_id: str, user=Depends(get_current_user)):
       if not has_permission(user.id, "PERM_PRODUCT_DELETE"):
           raise HTTPException(403, "Insufficient permissions")
       # Delete product
   ```

2. **Use Principle of Least Privilege**
   - Grant minimum permissions needed
   - Use temporary permissions for short-term access
   - Review and revoke unused permissions quarterly

3. **Protect Super Admin Role**
   ```python
   # Prevent removing last super admin
   def remove_role_from_user(user_id: str, role_id: str):
       if role_id == "ROLE_SUPER_ADMIN":
           remaining_admins = count_users_with_role("ROLE_SUPER_ADMIN")
           if remaining_admins <= 1:
               raise ValueError("Cannot remove last super admin")
   ```

4. **Log All Permission Changes**
   ```python
   audit_log = {
       "action": "permission_granted",
       "user_id": target_user_id,
       "permission_id": permission_id,
       "granted_by": admin_user_id,
       "timestamp": datetime.utcnow().isoformat(),
       "ip_address": request.client.host
   }
   audit_logs_table.put_item(Item=audit_log)
   ```

5. **Implement Rate Limiting**
   - Limit permission assignment API calls
   - Prevent brute-force role enumeration

### Common Pitfalls

1. **Frontend-Only Checks**
   - ❌ WRONG: Only hiding button in UI
   - ✅ CORRECT: Check permission on both frontend AND backend

2. **Overly Broad Permissions**
   - ❌ WRONG: Grant `ROLE_ADMIN` to everyone
   - ✅ CORRECT: Grant specific permissions as needed

3. **Not Invalidating Cache**
   - ❌ WRONG: User sees old permissions after role change
   - ✅ CORRECT: Invalidate cache when permissions change

4. **Hardcoded Permissions**
   - ❌ WRONG: `if user.role == "admin"`
   - ✅ CORRECT: `if has_permission(user_id, "PERM_PRODUCT_DELETE")`

---

## Migration Strategy

### Phase 1: Parallel Operation (Current)
**Status**: In Progress
**Timeline**: Q1 2025

- Keep existing `role` field in users table
- Add RBAC tables alongside (permissions, roles, user-permissions)
- Backend checks both legacy role and new permissions
- New features use RBAC, old features use legacy roles

**Code Example**:
```python
def check_access(user_id: str, required_permission: str) -> bool:
    # Check new RBAC system
    if has_permission(user_id, required_permission):
        return True

    # Fallback to legacy role check
    user = get_user_by_id(user_id)
    if user.role == "super_admin":
        return True

    return False
```

### Phase 2: Hybrid Mode
**Status**: Planned
**Timeline**: Q2 2025

- New features use ONLY permission checks
- Legacy features still support both
- Add `assigned_roles` field to users
- Map legacy roles to new role IDs:
  - `"super_admin"` → `"ROLE_SUPER_ADMIN"`
  - `"admin"` → `"ROLE_ADMIN"`
  - `"store_manager"` → `"ROLE_STORE_MANAGER"`

**Migration Script**:
```python
def migrate_legacy_roles():
    users = get_all_users()

    role_mapping = {
        "super_admin": "ROLE_SUPER_ADMIN",
        "admin": "ROLE_ADMIN",
        "store_manager": "ROLE_STORE_MANAGER"
    }

    for user in users:
        if user.role in role_mapping:
            new_role_id = role_mapping[user.role]
            assign_role_to_user(user.id, new_role_id, "migration_script")
```

### Phase 3: Full Migration
**Status**: Planned
**Timeline**: Q3 2025

- All features use permission-based checks
- Legacy `role` field marked as deprecated
- `assigned_roles` becomes primary role storage
- Remove legacy role checks from codebase

---

## Troubleshooting

### User Can't Access Feature Despite Having Permission

**Symptoms**: User has correct permission but gets 403 error

**Diagnosis**:
1. Check permission cache: `redis-cli GET user_permissions:{user_id}`
2. Verify permission assignment: Query `user-permissions` table
3. Check permission expiration: Look at `expires_at` field
4. Verify role is active: Check `status` field in roles table

**Solution**:
```python
# Invalidate and rebuild cache
invalidate_user_permissions_cache(user_id)
permissions = evaluate_user_permissions(user_id)
print(f"User has {len(permissions['permissions'])} permissions")
```

### Permission Changes Not Reflecting

**Symptoms**: User's permissions updated but old permissions still active

**Cause**: Cache not invalidated

**Solution**:
```python
# Force cache invalidation on permission change
def grant_permission_to_user(user_id: str, permission_id: str):
    # ... grant logic ...

    # ALWAYS invalidate cache
    invalidate_user_permissions_cache(user_id)

    # Optional: Force user to re-login
    revoke_all_user_sessions(user_id)
```

### Super Admin Locked Out

**Symptoms**: Cannot assign super admin role, no active super admins

**Prevention**:
```python
# Always maintain at least 2 super admins
def remove_role_from_user(user_id: str, role_id: str):
    if role_id == "ROLE_SUPER_ADMIN":
        active_admins = count_active_super_admins()
        if active_admins <= 1:
            raise ValueError("Cannot remove last super admin. Assign another super admin first.")
```

**Recovery**:
```python
# Emergency super admin assignment via AWS CLI
aws dynamodb update-item \
    --table-name vyaparai-users-prod \
    --key '{"id": {"S": "user_recovery@example.com"}}' \
    --update-expression "SET #role = :role" \
    --expression-attribute-names '{"#role": "role"}' \
    --expression-attribute-values '{":role": {"S": "super_admin"}}'
```

### Role Hierarchy Violation

**Symptoms**: User tries to assign a higher-level role and gets error

**Example**: Level 30 user tries to assign Level 10 role

**Solution**: This is by design. Only users at Level 10 or higher can assign Level 10 roles.

**Workaround**: Have a higher-level admin perform the assignment.

---

## Appendix

### Complete Permission List

| Permission ID | Category | Resource | Action | Description |
|---------------|----------|----------|--------|-------------|
| PERM_PRODUCT_CREATE | product_management | products | create | Create new products |
| PERM_PRODUCT_READ | product_management | products | read | View product details |
| PERM_PRODUCT_UPDATE | product_management | products | update | Edit existing products |
| PERM_PRODUCT_DELETE | product_management | products | delete | Remove products |
| PERM_PRODUCT_EXPORT | product_management | products | export | Export product data |
| PERM_PRODUCT_IMPORT_BULK | product_management | products | import | Bulk import products |
| PERM_USER_CREATE | user_management | users | create | Create new users |
| PERM_USER_READ | user_management | users | read | View user profiles |
| PERM_USER_UPDATE | user_management | users | update | Edit user details |
| PERM_USER_DELETE | user_management | users | delete | Deactivate users |
| PERM_USER_ASSIGN_ROLES | user_management | users | assign_roles | Assign roles to users |
| PERM_USER_ASSIGN_PERMISSIONS | user_management | users | assign_permissions | Grant direct permissions |
| PERM_ROLE_CREATE | role_management | roles | create | Create new roles |
| PERM_ROLE_READ | role_management | roles | read | View role definitions |
| PERM_ROLE_UPDATE | role_management | roles | update | Modify role permissions |
| PERM_ROLE_DELETE | role_management | roles | delete | Remove custom roles |
| PERM_ANALYTICS_VIEW | analytics | analytics | view | Access analytics dashboards |
| PERM_REPORTS_GENERATE | analytics | reports | generate | Generate custom reports |
| PERM_REPORTS_EXPORT | analytics | reports | export | Export reports to files |
| PERM_SETTINGS_VIEW | settings | settings | view | View system settings |
| PERM_SETTINGS_UPDATE | settings | settings | update | Modify app settings |
| PERM_SETTINGS_SYSTEM_CONFIG | settings | settings | configure | Change critical configs |

---

**Last Updated**: December 3, 2025
**Document Version**: 2.0.0
**Status**: Comprehensive Documentation - Architecture Complete, API Implementation Pending
**Related Files**:
- Implementation: `/backend/app/services/rbac_service.py`
- Frontend: `/frontend-pwa/src/contexts/AuthContext.tsx`
- Database: See `DATABASE_SCHEMA_DOCUMENTATION.md` Section 11
