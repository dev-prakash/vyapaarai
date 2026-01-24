# Critical Fixes Implementation Guide

## Overview
This guide provides step-by-step fixes for the 8 critical issues identified in the audit. Implement these in order as they have dependencies.

---

## Fix #1: Create Centralized Token Manager (6-8 hours)
**Blocks:** Fixes critical issues #3, #4, partial #7

### Create: `src/utils/tokenManager.ts`

```typescript
/**
 * Centralized Token Management
 * Single source of truth for all authentication tokens
 */

// All valid token keys (for reference/cleanup)
const ALL_TOKEN_KEYS = [
  'vyaparai_token',
  'vyaparai_user_type',
  'vyaparai_user_data',
  'vyaparai_auth_token',
  'vyaparai_customer_token',
  'customer_token',
  'auth_token',
  'vyaparai_auth_user',
  'user_data',
  'vyaparai-auth',
  'customer_profile'
] as const;

export interface TokenData {
  token: string;
  userType: 'customer' | 'store_owner' | 'admin' | 'super_admin';
  userData: any;
}

class TokenManager {
  private readonly TOKEN_KEY = 'vyaparai_token';
  private readonly USER_TYPE_KEY = 'vyaparai_user_type';
  private readonly USER_DATA_KEY = 'vyaparai_user_data';

  /**
   * Get current token
   */
  getToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  /**
   * Get current user type
   */
  getUserType(): string | null {
    return localStorage.getItem(this.USER_TYPE_KEY);
  }

  /**
   * Get current user data
   */
  getUserData(): any {
    const data = localStorage.getItem(this.USER_DATA_KEY);
    if (!data) return null;
    
    try {
      return JSON.parse(data);
    } catch (e) {
      console.error('Failed to parse user data:', e);
      this.clearAll();
      return null;
    }
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    const token = this.getToken();
    const userType = this.getUserType();
    return !!(token && userType);
  }

  /**
   * Set tokens - THE ONLY WAY TO SET TOKENS
   */
  setTokens(token: string, userType: string, userData: any): void {
    try {
      localStorage.setItem(this.TOKEN_KEY, token);
      localStorage.setItem(this.USER_TYPE_KEY, userType);
      localStorage.setItem(this.USER_DATA_KEY, JSON.stringify(userData));
      
      // Clean up old token keys
      this.clearLegacyTokens();
      
      console.log('[TokenManager] Tokens set successfully for:', userType);
    } catch (e) {
      console.error('[TokenManager] Failed to set tokens:', e);
      // If quota exceeded, clear all and try again
      this.clearAll();
      localStorage.setItem(this.TOKEN_KEY, token);
      localStorage.setItem(this.USER_TYPE_KEY, userType);
      localStorage.setItem(this.USER_DATA_KEY, JSON.stringify(userData));
    }
  }

  /**
   * Clear all tokens - THE ONLY WAY TO CLEAR TOKENS
   */
  clearAll(): void {
    ALL_TOKEN_KEYS.forEach(key => {
      try {
        localStorage.removeItem(key);
      } catch (e) {
        // Ignore errors
      }
    });
    console.log('[TokenManager] All tokens cleared');
  }

  /**
   * Validate token integrity
   */
  validateTokens(): boolean {
    const token = this.getToken();
    const userType = this.getUserType();
    const userData = this.getUserData();

    // Must have all three
    if (!token || !userType || !userData) {
      if (token || userType || userData) {
        // Partial tokens - invalid state
        console.error('[TokenManager] Partial tokens found - clearing all');
        this.clearAll();
      }
      return false;
    }

    // Token should be at least 20 chars (rough validation)
    if (token.length < 20) {
      console.error('[TokenManager] Invalid token length');
      this.clearAll();
      return false;
    }

    // UserType should be valid
    const validTypes = ['customer', 'store_owner', 'admin', 'super_admin'];
    if (!validTypes.includes(userType)) {
      console.error('[TokenManager] Invalid user type:', userType);
      this.clearAll();
      return false;
    }

    return true;
  }

  /**
   * Clean up legacy token keys
   */
  private clearLegacyTokens(): void {
    const legacyKeys = [
      'vyaparai_auth_token',
      'vyaparai_customer_token',
      'customer_token',
      'auth_token',
      'vyaparai_auth_user',
      'user_data',
      'vyaparai-auth',
      'customer_profile'
    ];
    
    legacyKeys.forEach(key => {
      try {
        localStorage.removeItem(key);
      } catch (e) {
        // Ignore
      }
    });
  }
}

// Singleton instance
export const tokenManager = new TokenManager();

export default tokenManager;
```

### Update: `src/services/apiClient.ts`

Replace the 401 error handling to use tokenManager:

```typescript
// OLD CODE - DELETE
localStorage.removeItem('vyaparai_auth_token');
localStorage.removeItem('auth_token');
// ... more removes

// NEW CODE - ADD
import { tokenManager } from '../utils/tokenManager';

// In response interceptor 401 handler:
if (error.response?.status === 401 && !isLoginEndpoint) {
  tokenManager.clearAll();  // Clear ALL tokens at once
  
  // Determine redirect
  const userType = tokenManager.getUserType();
  const currentPath = window.location.pathname;
  
  const redirects = {
    admin: '/nimdaaccess',
    super_admin: '/nimdaaccess',
    store_owner: '/store-login',
    customer: '/login'
  };
  
  const redirectPath = currentPath.startsWith('/admin') 
    ? '/nimdaaccess'
    : redirects[userType as keyof typeof redirects] || '/login';
  
  window.location.href = redirectPath;
}
```

### Update: `src/stores/authStore.ts`

```typescript
import { tokenManager } from '../utils/tokenManager';

// Remove module-level initialization
// DELETE THIS: useAuthStore.getState().checkAuth();

// Instead, in the store:
checkAuth: () => {
  // Use tokenManager as source of truth
  if (tokenManager.isAuthenticated()) {
    set({
      user: tokenManager.getUserData(),
      isAuthenticated: true
    });
  } else {
    set({
      user: null,
      isAuthenticated: false
    });
  }
},

signOut: async () => {
  set({ isLoading: true });
  await authService.signOut();
  tokenManager.clearAll();  // Use centralized clear
  set({ user: null, isAuthenticated: false, isLoading: false });
}
```

### Update: `src/App.tsx`

Add proper initialization:

```typescript
function App() {
  const { user, checkAuth } = useAppStore();
  
  // Initialize auth on mount
  useEffect(() => {
    checkAuth();  // Now safe to call from effect
  }, [checkAuth]);
  
  return (/* ... */);
}
```

---

## Fix #2: Fix Cart Race Condition (4-6 hours)
**Blocks:** Loss of data on concurrent cart operations

### Create: `src/utils/actionQueue.ts`

```typescript
/**
 * Action queue to prevent race conditions
 */

type ActionFn<T = any> = () => Promise<T>;

class ActionQueue {
  private queue: Array<{ fn: ActionFn; resolve: Function; reject: Function }> = [];
  private isProcessing = false;

  /**
   * Queue an action to be processed sequentially
   */
  async enqueue<T>(fn: ActionFn<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      this.queue.push({ fn, resolve, reject });
      this.process();
    });
  }

  /**
   * Process queue items sequentially
   */
  private async process(): Promise<void> {
    if (this.isProcessing || this.queue.length === 0) return;

    this.isProcessing = true;

    while (this.queue.length > 0) {
      const { fn, resolve, reject } = this.queue.shift()!;

      try {
        const result = await fn();
        resolve(result);
      } catch (error) {
        reject(error);
      }
    }

    this.isProcessing = false;
  }

  /**
   * Get queue length
   */
  length(): number {
    return this.queue.length;
  }

  /**
   * Clear queue
   */
  clear(): void {
    this.queue = [];
    this.isProcessing = false;
  }
}

export const createActionQueue = () => new ActionQueue();
```

### Update: `src/stores/cartStore.ts`

```typescript
import { createActionQueue } from '../utils/actionQueue';

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => {
      // Create queue for sequential operations
      const actionQueue = createActionQueue();

      return {
        // ... existing code ...

        addItem: async (product, quantity) => {
          return actionQueue.enqueue(async () => {
            const { storeId } = get();
            if (!storeId) {
              console.error('Store ID not set');
              return;
            }

            // Optimistic update
            set((state) => {
              const existingItem = state.items.find(item => item.id === product.id);
              
              if (existingItem) {
                const newQuantity = Math.min(
                  existingItem.quantity + quantity,
                  product.current_stock
                );
                return {
                  items: state.items.map(item =>
                    item.id === product.id
                      ? { ...item, quantity: newQuantity }
                      : item
                  ),
                };
              }
              
              const newItem: CartItem = {
                id: product.id,
                name: product.product_name || product.name,
                price: product.selling_price || product.price,
                quantity: Math.min(quantity, product.current_stock),
                unit: product.size_unit || product.unit || 'piece',
                brand: product.brand_name || product.brand,
                category: product.category_name || product.category,
                image: product.image_urls?.thumbnail || product.image,
                maxQuantity: product.current_stock,
              };
              
              return { items: [...state.items, newItem] };
            });

            // Backend sync - no rollback needed since queue is sequential
            try {
              set({ syncing: true });
              await backendCartService.addToCart(storeId, product.id, quantity);
              set({ syncing: false });
            } catch (error) {
              console.error('Backend sync failed:', error);
              // Remove item only if backend failed
              set((state) => ({
                items: state.items.filter(item => item.id !== product.id),
                syncing: false,
              }));
              throw error;
            }
          });
        },

        // Similar pattern for updateQuantity and removeItem...
      };
    },
    {
      name: 'vyaparai-cart',
      partialize: (state) => ({
        items: state.items,
        customerInfo: state.customerInfo,
        storeId: state.storeId,
      }),
    }
  )
);
```

---

## Fix #3: Unsafe JSON.parse Recovery (2-3 hours)
**Blocks:** App recovery from corrupted localStorage

### Update: `src/stores/unifiedAuthStore.ts`

```typescript
const getStoredSession = (): { token: string | null; userType: UserType | null; userData: User | null } => {
  const token = localStorage.getItem(TOKEN_KEYS.MAIN)
  const userType = localStorage.getItem(TOKEN_KEYS.USER_TYPE) as UserType | null
  const userDataStr = localStorage.getItem(TOKEN_KEYS.USER_DATA)
  
  let userData: User | null = null
  if (userDataStr) {
    try {
      userData = JSON.parse(userDataStr)
    } catch (e) {
      console.error('Failed to parse stored user data:', e)
      
      // CRITICAL: Clear all tokens on parse error
      clearLegacyTokens()
      localStorage.removeItem(TOKEN_KEYS.MAIN)
      localStorage.removeItem(TOKEN_KEYS.USER_TYPE)
      localStorage.removeItem(TOKEN_KEYS.USER_DATA)
      
      // Return null values so app redirects to login
      return { token: null, userType: null, userData: null }
    }
  }
  
  return { token, userType, userData }
}
```

---

## Fix #4: Enable TypeScript Strict Mode (20-30 hours)
**Blocks:** 50+ type-related bugs

### Update: `tsconfig.json`

```json
{
  "compilerOptions": {
    "strict": true,  // WAS: false
    "noUnusedLocals": true,  // WAS: false
    "noUnusedParameters": true,  // WAS: false
    "noImplicitAny": true,  // ADD
    "strictNullChecks": true,  // ADD
    // ... rest of config
  }
}
```

### Action Plan:
1. Run `npm run type-check` to see all errors
2. Create GitHub issue with the error list
3. Fix errors file by file, starting with src/stores/
4. Remove all `@ts-nocheck` comments
5. Replace `any` types with proper types

---

## Fix #5: Session Initialization Race Condition (2-3 hours)
**Blocks:** Protected routes rendering before auth check

### Update: `src/App.tsx`

```typescript
import { useEffect } from 'react';
import { useAppStore } from '@store/appStore';
import { CircularProgress, Box } from '@mui/material';

function App() {
  const { user, isAuthenticated, isLoading, checkAuth } = useAppStore();
  
  // Initialize auth on mount
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);
  
  // Show loading while checking auth
  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh'
        }}
      >
        <CircularProgress />
      </Box>
    );
  }
  
  return (
    // ... routes ...
  );
}
```

### Update: `src/stores/authStore.ts`

Remove module-level initialization:

```typescript
// DELETE THIS LINE:
// useAuthStore.getState().checkAuth();
```

---

## Fix #6: Sensitive Data Exposure (3-5 hours)
**Blocks:** Security vulnerability from localStorage exposure

### Update: `src/services/authService.ts`

```typescript
// OLD - Stores full customer object
localStorage.setItem('customer_profile', JSON.stringify(customer));

// NEW - Store only necessary data
localStorage.setItem('customer_id', customer.customer_id);
localStorage.setItem('customer_token', response.data.token);

// Fetch full profile from API when needed
async getCustomerProfile(): Promise<CustomerUser> {
  const response = await apiClient.get('/api/v1/customer/auth/profile');
  return response.data.customer;
}
```

### Update: `src/utils/sessionManager.ts`

Add function to safely get customer data:

```typescript
export const sessionManager = {
  // ... existing code ...
  
  getCustomerId(): string | null {
    return localStorage.getItem('customer_id');
  },
  
  // Only store token in localStorage
  saveCustomerToken(token: string, customerId: string): void {
    localStorage.setItem('customer_token', token);
    localStorage.setItem('customer_id', customerId);
    // Don't store profile
  }
};
```

---

## Fix #7: useWebSocket Unhandled Promises (2-3 hours)
**Blocks:** Memory leaks from unresolved promises

### Update: `src/hooks/useWebSocket.ts`

```typescript
// OLD:
socket.on('connect', () => {
  // ...
  toast.success('Connected to server')
  processMessageQueue()  // Unhandled promise!
  processActionQueue()   // Unhandled promise!
})

// NEW:
socket.on('connect', async () => {
  // ...
  toast.success('Connected to server')
  
  try {
    await processMessageQueue();
    await processActionQueue();
  } catch (error) {
    console.error('Failed to process queues:', error);
    toast.error('Failed to sync with server');
  }
})
```

---

## Fix #8: Cart Migration Missing Validation (2-3 hours)
**Blocks:** Potential data loss during guest to auth migration

### Update: `src/stores/cartStore.ts`

```typescript
migrateGuestCart: async (guestSessionId, storeId) => {
  try {
    console.log('[CartStore] Migrating guest cart:', guestSessionId);
    set({ syncing: true });

    // Validate inputs
    if (!guestSessionId || typeof guestSessionId !== 'string') {
      console.warn('[CartStore] Invalid guest session ID');
      set({ syncing: false });
      return;
    }

    const result = await backendCartService.migrateCart(
      guestSessionId,
      storeId,
      'merge'
    );

    if (result && result.success) {
      console.log(`[CartStore] Migration successful: ${result.migratedCarts} cart(s)`);

      // Validate and use migration result
      if (result.details && Array.isArray(result.details) && result.details.length > 0) {
        const firstStore = result.details[0];
        
        // CRITICAL: Validate store_id exists before using
        if (firstStore && typeof firstStore === 'object' && firstStore.store_id) {
          try {
            await get().syncWithBackend(firstStore.store_id);
          } catch (syncError) {
            console.error('[CartStore] Failed to sync after migration:', syncError);
            // Continue anyway - user can refresh to sync
          }
        } else {
          console.warn('[CartStore] Migration succeeded but store_id missing');
        }
      }

      set({ syncing: false });
    } else if (result === null) {
      console.log('[CartStore] Migration endpoint not available');
      if (storeId) {
        await get().syncWithBackend(storeId);
      }
      set({ syncing: false });
    } else {
      console.warn('[CartStore] Migration completed but no carts migrated');
      set({ syncing: false });
    }
  } catch (error) {
    console.error('[CartStore] Failed to migrate guest cart:', error);
    set({ syncing: false });
    // Don't throw - allow app to continue with new session
  }
}
```

---

## Implementation Order

**Week 1:**
1. Fix #1 - Token Manager (8h) - FOUNDATION
2. Fix #2 - Cart Race Condition (6h) - DATA SAFETY
3. Fix #3 - JSON Parse Recovery (3h) - ERROR HANDLING
4. Fix #5 - Auth Initialization (3h) - ROUTING SAFETY

**Week 2:**
5. Fix #4 - TypeScript Strict Mode (30h) - TYPE SAFETY
6. Fix #8 - Cart Migration Validation (3h) - DATA INTEGRITY

**Week 3:**
7. Fix #6 - Sensitive Data Exposure (5h) - SECURITY
8. Fix #7 - WebSocket Promises (3h) - MEMORY LEAKS

**Total:** ~68 hours for all critical fixes

---

## Testing Checklist After Fixes

After implementing each fix, test:

- [ ] Login/logout works correctly
- [ ] Session persists across page refresh
- [ ] Guest cart migrates to authenticated user
- [ ] Multiple cart operations don't cause data loss
- [ ] Corrupted localStorage doesn't break app
- [ ] 401 errors clear all tokens
- [ ] TypeScript compilation with no errors
- [ ] No sensitive data in browser storage

---

## Validation Script

Run this to verify fixes:

```bash
# Check TypeScript
npm run type-check

# Check for console errors
npm run build 2>&1 | grep -i error

# Check localStorage usage
grep -r "localStorage.setItem" src/ | grep -v "token" | grep -v "session"

# Check for @ts-ignore
grep -r "@ts-ignore" src/

# Check for @ts-nocheck
grep -r "@ts-nocheck" src/
```
