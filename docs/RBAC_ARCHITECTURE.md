# VyapaarAI RBAC (Role-Based Access Control) Architecture

## Overview

VyapaarAI implements a comprehensive RBAC system to manage user permissions and access control across the platform. The system supports both role-based and direct permission assignment with granular control.

## Database Schema

### 1. **vyaparai-users-prod** (Enhanced Existing Table)
Primary user authentication and profile table.

**Primary Key:** `id` (String) - Format: `user_{email}`

**Attributes:**
- `id`: User identifier
- `email`: User email address
- `name`: Full name
- `password_hash`: Bcrypt hashed password
- `password_algorithm`: "bcrypt" or "sha256"
- `role`: Legacy role field ("super_admin", "admin", "store_manager", etc.)
- `status`: "active" | "inactive" | "suspended"
- `created_at`: ISO timestamp
- `updated_at`: ISO timestamp
- `last_login`: ISO timestamp
- `failed_attempts`: Number of failed login attempts
- `locked_until`: Account lock timestamp

**RBAC Extensions (Future):**
- `assigned_roles`: List of role IDs
- `assigned_permissions`: List of direct permission IDs
- `permission_overrides`: Map of permission overrides

---

### 2. **vyaparai-permissions-prod** (New)
Stores individual permission definitions.

**Primary Key:** `permission_id` (String)

**Attributes:**
- `permission_id`: Unique permission identifier (e.g., "PERM_PRODUCT_CREATE")
- `name`: Human-readable name (e.g., "Create Products")
- `description`: Detailed description of what this permission allows
- `category`: Permission category ("product_management" | "user_management" | "role_management" | "analytics" | "settings")
- `resource`: Target resource (e.g., "products", "users", "roles")
- `action`: Action type ("create" | "read" | "update" | "delete" | "export" | "import" | "configure")
- `status`: "active" | "deprecated"
- `created_at`: ISO timestamp
- `updated_at`: ISO timestamp

**GSI - CategoryIndex:**
- PK: `category`
- SK: `status`
- Use: Query all active permissions in a category

**Seeded Permissions (22 total):**
- **Product Management:** CREATE, READ, UPDATE, DELETE, EXPORT, IMPORT_BULK
- **User Management:** CREATE, READ, UPDATE, DELETE, ASSIGN_ROLES, ASSIGN_PERMISSIONS
- **Role Management:** CREATE, READ, UPDATE, DELETE
- **Analytics:** VIEW, REPORTS_GENERATE, REPORTS_EXPORT
- **Settings:** VIEW, UPDATE, SYSTEM_CONFIG

---

### 3. **vyaparai-roles-prod** (New)
Stores role definitions with associated permissions.

**Primary Key:** `role_id` (String)

**Attributes:**
- `role_id`: Unique role identifier (e.g., "ROLE_SUPER_ADMIN")
- `role_name`: Human-readable role name (e.g., "Super Administrator")
- `description`: Role description
- `permissions`: StringSet of permission IDs (or ["*"] for all permissions)
- `hierarchy_level`: Number (1-100, lower = higher privilege)
- `is_system_role`: Boolean (system roles cannot be deleted)
- `status`: "active" | "inactive"
- `created_at`: ISO timestamp
- `updated_at`: ISO timestamp

**GSI - HierarchyIndex:**
- PK: `status`
- SK: `hierarchy_level`
- Use: Query all active roles sorted by hierarchy

**Seeded Roles (5 total):**
1. **ROLE_SUPER_ADMIN** (Level 1)
   - All permissions (["*"])
   - System role

2. **ROLE_ADMIN** (Level 10)
   - Product management (all)
   - User view/update
   - Analytics & reports
   - Settings view
   - System role

3. **ROLE_STORE_MANAGER** (Level 20)
   - Product read/update/export
   - Analytics view
   - Reports generate
   - System role

4. **ROLE_CATALOG_EDITOR** (Level 30)
   - Product CRUD + export
   - Custom role

5. **ROLE_VIEWER** (Level 50)
   - Product read
   - Analytics view
   - Custom role

---

### 4. **vyaparai-user-permissions-prod** (New)
Junction table tracking user-permission assignments with audit trail.

**Primary Key:** `assignment_id` (String) - Format: `{user_id}#{permission_id}`

**Attributes:**
- `assignment_id`: Composite key
- `user_id`: User identifier
- `permission_id`: Permission identifier
- `granted_by`: User ID who granted this permission
- `assignment_type`: "direct" | "role_inherited" | "override"
- `expires_at`: Optional expiration timestamp
- `assigned_at`: ISO timestamp

**GSI1 - UserPermissionsIndex:**
- PK: `user_id`
- SK: `assignment_type`
- Use: Query all permissions for a user

**GSI2 - PermissionUsersIndex:**
- PK: `permission_id`
- Use: Query all users with a specific permission

---

## Permission Evaluation Logic

```javascript
function evaluateUserPermissions(userId) {
  // 1. Check if super admin
  const user = getUserById(userId);
  if (user.role === 'super_admin') {
    return { hasFullAccess: true, permissions: ['*'] };
  }

  // 2. Get user's assigned roles
  const userRoles = user.assigned_roles || [];

  // 3. Collect permissions from roles
  let permissionsFromRoles = new Set();
  for (const roleId of userRoles) {
    const role = getRoleById(roleId);
    if (role.permissions.includes('*')) {
      return { hasFullAccess: true, permissions: ['*'] };
    }
    role.permissions.forEach(p => permissionsFromRoles.add(p));
  }

  // 4. Get direct permissions
  const directPermissions = user.assigned_permissions || [];

  // 5. Merge all permissions
  const allPermissions = new Set([
    ...permissionsFromRoles,
    ...directPermissions
  ]);

  // 6. Apply overrides (deny takes precedence)
  if (user.permission_overrides) {
    for (const [perm, allowed] of Object.entries(user.permission_overrides)) {
      if (!allowed) {
        allPermissions.delete(perm);
      } else {
        allPermissions.add(perm);
      }
    }
  }

  return {
    hasFullAccess: false,
    permissions: Array.from(allPermissions)
  };
}

function hasPermission(userId, permissionId) {
  const { hasFullAccess, permissions } = evaluateUserPermissions(userId);
  return hasFullAccess || permissions.includes(permissionId);
}
```

---

## Permission Naming Convention

**Format:** `PERM_{RESOURCE}_{ACTION}`

**Examples:**
- `PERM_PRODUCT_CREATE`
- `PERM_USER_UPDATE`
- `PERM_ROLE_DELETE`
- `PERM_ANALYTICS_VIEW`

**Resources:** PRODUCT, USER, ROLE, ANALYTICS, REPORTS, SETTINGS, SYSTEM

**Actions:** CREATE, READ, UPDATE, DELETE, EXPORT, IMPORT, CONFIGURE, VIEW, GENERATE, ASSIGN_ROLES, ASSIGN_PERMISSIONS

---

## Role Naming Convention

**Format:** `ROLE_{ROLE_NAME}`

**Examples:**
- `ROLE_SUPER_ADMIN`
- `ROLE_ADMIN`
- `ROLE_STORE_MANAGER`
- `ROLE_CATALOG_EDITOR`

---

## Role Hierarchy

Roles are organized by hierarchy level to prevent privilege escalation:

1. **Level 1-9:** Super Admin level
2. **Level 10-19:** Admin level
3. **Level 20-29:** Manager level
4. **Level 30-49:** Editor/Contributor level
5. **Level 50-99:** Viewer/Guest level

**Rules:**
- Users can only assign roles at their level or lower
- Users cannot modify roles at their level or higher
- System roles (is_system_role: true) cannot be deleted

---

## Usage Examples

### Backend - Check Permission

```python
def check_permission(user_id: str, permission: str) -> bool:
    """Check if user has specific permission"""
    user = get_user_by_id(user_id)

    # Super admin bypass
    if user.get('role') == 'super_admin':
        return True

    # Get user permissions from cache or evaluate
    user_permissions = evaluate_user_permissions(user_id)

    return permission in user_permissions or '*' in user_permissions
```

### Frontend - Conditional Rendering

```typescript
interface PermissionGuardProps {
  permission: string;
  children: React.ReactNode;
}

const PermissionGuard: React.FC<PermissionGuardProps> = ({ permission, children }) => {
  const { userPermissions } = useAuth();

  if (!userPermissions.includes(permission) && !userPermissions.includes('*')) {
    return null;
  }

  return <>{children}</>;
};

// Usage
<PermissionGuard permission="PERM_PRODUCT_CREATE">
  <Button onClick={createProduct}>Create Product</Button>
</PermissionGuard>
```

---

## Migration Strategy

### Phase 1: Parallel Operation (Current)
- Keep existing `role` field in users table
- Add RBAC tables alongside
- Backend checks both legacy role and new permissions
- Gradual migration of features to permission-based checks

### Phase 2: Hybrid Mode
- New features use only permission checks
- Legacy features still support both
- Add `assigned_roles` field to users
- Map legacy roles to new role IDs

### Phase 3: Full Migration
- All features use permission-based checks
- Legacy `role` field marked as deprecated
- `assigned_roles` becomes primary role storage
- Remove legacy role checks from codebase

---

## API Endpoints (To Be Implemented)

### Permissions Management
```
GET    /api/v1/admin/permissions              - List all permissions
GET    /api/v1/admin/permissions/:id           - Get permission details
POST   /api/v1/admin/permissions               - Create permission (super admin only)
PUT    /api/v1/admin/permissions/:id           - Update permission
DELETE /api/v1/admin/permissions/:id           - Delete permission
```

### Roles Management
```
GET    /api/v1/admin/roles                     - List all roles
GET    /api/v1/admin/roles/:id                 - Get role details
POST   /api/v1/admin/roles                     - Create role
PUT    /api/v1/admin/roles/:id                 - Update role
DELETE /api/v1/admin/roles/:id                 - Delete role (non-system only)
POST   /api/v1/admin/roles/:id/permissions     - Assign permissions to role
```

### User Permissions
```
GET    /api/v1/admin/users/:id/permissions     - Get user's effective permissions
POST   /api/v1/admin/users/:id/permissions     - Assign direct permissions
DELETE /api/v1/admin/users/:id/permissions/:pid - Remove permission
POST   /api/v1/admin/users/:id/roles           - Assign role to user
DELETE /api/v1/admin/users/:id/roles/:rid      - Remove role from user
```

---

## Security Considerations

1. **Audit Trail:** All permission assignments tracked in user-permissions table
2. **Temporal Permissions:** Support for expiring permissions via `expires_at`
3. **Principle of Least Privilege:** Default to minimal permissions
4. **Hierarchy Enforcement:** Prevent privilege escalation via role levels
5. **Super Admin Protection:** Super admin role cannot be removed from last super admin
6. **System Role Protection:** System roles cannot be deleted or drastically modified

---

## Future Enhancements

1. **Resource-Level Permissions:** Permissions scoped to specific resources (e.g., "PERM_PRODUCT_UPDATE:store_123")
2. **Dynamic Permissions:** Runtime permission creation without code changes
3. **Permission Groups:** Logical grouping of related permissions
4. **Multi-Tenancy:** Store-specific permission scopes
5. **Permission Templates:** Pre-defined permission sets for common scenarios
6. **Approval Workflows:** Require approval for sensitive permission grants
7. **Time-Based Access:** Schedule-based permission activation

---

## Maintenance

### Adding New Permissions

1. Define permission in seed data or via API
2. Update backend checks in relevant endpoints
3. Update frontend components with PermissionGuard
4. Assign to appropriate roles
5. Document in this file

### Creating New Roles

1. Define role with permissions list
2. Set appropriate hierarchy level
3. Mark as system role if needed
4. Add to seed data or create via API
5. Document use case and permission scope

---

## Summary

**Tables Created:**
- ✅ vyaparai-permissions-prod (22 permissions)
- ✅ vyaparai-roles-prod (5 roles)
- ✅ vyaparai-user-permissions-prod (junction table)

**Benefits:**
- Granular access control
- Audit trail for all permission changes
- Flexible role definitions
- Scalable for future growth
- Multi-tenancy ready

**Status:** Architecture implemented, frontend UI ready, backend API endpoints pending implementation.

---

*Last Updated: 2025-10-02*
*Version: 1.0.0*
