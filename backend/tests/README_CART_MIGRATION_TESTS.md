# Cart Migration API Test Suite

Comprehensive test suite for the cart migration functionality in VyaparAI.

## Overview

This test suite covers:
- ✅ Authentication requirements
- ✅ All merge strategies (merge, replace, keep_newest)
- ✅ Single store migration
- ✅ Multi-store migration
- ✅ Get all carts endpoint
- ✅ Guest cart cleanup
- ✅ Rate limiting
- ✅ Input validation
- ✅ Error handling
- ✅ Response structure validation
- ✅ Concurrent requests

## Prerequisites

```bash
pip install httpx pytest pytest-asyncio
```

## Running Tests

### Against Local Development Server

1. Start your local API server:
```bash
cd /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend
uvicorn app.main:app --reload --port 8000
```

2. Run the tests:
```bash
cd /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend
python tests/test_cart_migration.py
```

### Against Production API

```bash
export API_BASE_URL=https://api.vyaparai.com
python tests/test_cart_migration.py
```

### Using pytest

```bash
# Run all cart migration tests
pytest tests/test_cart_migration.py -v

# Run specific test function
pytest tests/test_cart_migration.py::test_migration_merge_strategies -v

# Run with detailed output
pytest tests/test_cart_migration.py -vv -s
```

## Test Configuration

### Environment Variables

- `API_BASE_URL`: Base URL of the API (default: `http://localhost:8000`)
- Example: `export API_BASE_URL=https://api.vyaparai.com`

### Authentication

Tests require a valid customer authentication token. The test suite attempts to:
1. Get a token from your customer auth endpoint
2. Falls back to a mock token if auth endpoint is unavailable

**For production testing**, you'll need to:
1. Update the `get_test_auth_token()` method with your actual customer auth flow
2. Or manually set a valid token in the test code

## Test Coverage

### Authentication Tests
- ✅ Migration without auth token (should fail with 401/403)
- ✅ Migration with invalid token (should fail with 401)
- ✅ Migration with valid token (should succeed)

### Merge Strategy Tests
Each strategy is tested independently:
- **merge**: Combines items from both carts, adding quantities for duplicates
- **replace**: Guest cart completely replaces user cart
- **keep_newest**: Most recently updated cart wins

### Migration Scenarios
- ✅ Single store migration (with store_id parameter)
- ✅ All stores migration (without store_id parameter)
- ✅ Migration with no guest carts (graceful 404 handling)
- ✅ Concurrent migration requests

### Endpoint Tests
- ✅ `POST /api/v1/cart/migrate` - Main migration endpoint
- ✅ `GET /api/v1/cart/all` - Get all customer carts
- ✅ `DELETE /api/v1/cart/cleanup-guest/{session_id}` - Cleanup guest carts

### Error Handling Tests
- ✅ Missing required fields (422 validation error)
- ✅ Invalid merge strategy (422 validation error)
- ✅ Invalid guest session ID format
- ✅ Rate limiting (429 too many requests)

### Response Validation
- ✅ Correct HTTP status codes
- ✅ Response structure validation
- ✅ Required fields present
- ✅ Proper data types

## Expected Results

### Successful Migration Response
```json
{
  "status": "success",
  "migrated_carts": 1,
  "message": "Successfully migrated 1 cart(s)",
  "details": [
    {
      "store_id": "STORE-TEST-001",
      "success": true,
      "message": "Cart migrated successfully with merge strategy"
    }
  ]
}
```

### No Carts Found Response
```json
{
  "status": "no_carts_found",
  "migrated_carts": 0,
  "message": "No guest carts found for the provided session ID",
  "details": []
}
```

### Rate Limit Response
```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

## Troubleshooting

### Connection Refused
```
❌ Could not connect to http://localhost:8000
```
**Solution**: Make sure your API server is running on the correct port.

### Authentication Failures
```
Status Code: 401
{"detail": "Could not validate credentials"}
```
**Solution**: Update the `get_test_auth_token()` method with your actual auth flow or provide a valid token.

### Rate Limiting Kicks In
```
Request 6: Status 429
```
**Solution**: This is expected behavior. Wait 60 seconds or adjust rate limits in code.

### Test Database Conflicts
If tests create conflicting data, you may want to:
1. Use a separate test DynamoDB table
2. Clean up test data after each run
3. Use unique session IDs with timestamps

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run Cart Migration Tests
  run: |
    cd backend
    pip install -r requirements.txt
    python tests/test_cart_migration.py
  env:
    API_BASE_URL: ${{ secrets.API_BASE_URL }}
    TEST_AUTH_TOKEN: ${{ secrets.TEST_AUTH_TOKEN }}
```

### AWS CodeBuild Example
```yaml
phases:
  test:
    commands:
      - cd backend
      - python tests/test_cart_migration.py
```

## Adding New Tests

To add new test cases:

1. Create a new async function following the naming convention:
```python
async def test_your_new_test(base_url: str, auth_token: str):
    print_header("YOUR NEW TEST")
    # Test implementation
```

2. Add it to the main() function:
```python
await test_your_new_test(base_url, auth_token)
```

3. Add to the test summary:
```python
print("✓ Your new test passed")
```

## Performance Benchmarks

Expected response times:
- Migration endpoint: < 500ms
- Get all carts: < 300ms
- Cleanup endpoint: < 200ms

## Notes

- Tests are designed to be **non-destructive** and can run against production
- Guest carts with test session IDs are automatically cleaned up
- Rate limiting is tested but won't affect subsequent runs (60-second window)
- All assertions use explicit status code checks for clarity

## Support

For issues or questions:
- Check the main API documentation at `/docs` endpoint
- Review CloudWatch logs for detailed error messages
- Verify DynamoDB table permissions and structure

---

**Last Updated**: 2025-11-21
**Test Coverage**: 10 test functions, ~50 assertions
**Estimated Run Time**: 30-45 seconds
