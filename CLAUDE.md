# VyapaarAI - Project Configuration

## Developer: DevPrakash

## Git Configuration
- Name: DevPrakash
- Email: dev.prakash@gmail.com
- Repository: https://github.com/dev-prakash/vyapaarai

---

## Slash Commands

### Branch Management
| Command | Description |
|---------|-------------|
| `/feature <name>` | Create feature branch: `./scripts/new_feature.sh <name>` |
| `/fix <name>` | Create fix branch: `./scripts/new_fix.sh <name>` |
| `/finish` | Merge to develop: `./scripts/finish_feature.sh` |
| `/release <ver>` | Release to main: `./scripts/release.sh <ver>` |

### Testing
| Command | Description |
|---------|-------------|
| `/test unit` | Run unit tests |
| `/test regression` | Run regression tests |
| `/test coverage` | Run with coverage |
| `/test all` | Run all tests |
| `/deploy-check` | Pre-deploy verification |

### Git
| Command | Description |
|---------|-------------|
| `/commit "<msg>"` | Stage all and commit |
| `/push` | Push current branch |
| `/status` | Show git status |
| `/sync` | Pull current branch |

### Test Generation
| Command | Description |
|---------|-------------|
| `/generate-test <file>` | Generate unit tests for file |
| `/generate-test-bugfix <file> "<bug>"` | Generate regression tests for bug fix |

---

## Commit Format
```
<type>: <description>

Types: feat, fix, refactor, test, docs, chore
```

---

## Branch Strategy

```
main ─────────────────────────────────────────────
  │                            ▲
  │                            │ release
  ▼                            │
develop ──────────────────────────────────────────
  │         ▲         ▲
  │         │ merge   │ merge
  ▼         │         │
feature/x ──┘         │
                      │
fix/y ────────────────┘
```

---

## Test Standards

### Markers
- `@pytest.mark.unit` - Fast isolated tests
- `@pytest.mark.regression` - Critical path tests (MUST pass before deploy)
- `@pytest.mark.integration` - Tests requiring external services

### Naming Convention
```
test_<function>_<scenario>_<expected_result>
```

### Example Test Structure
```python
@pytest.mark.unit
def test_create_order_with_valid_items_returns_order_id(self, dynamodb_mock):
    # Arrange
    # Act  
    # Assert
    pass

@pytest.mark.regression
def test_cancel_order_restores_inventory(self, dynamodb_mock):
    """CRITICAL: Verify inventory is restored on cancellation"""
    pass
```

---

## Project Structure

```
vyapaarai/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   ├── core/            # Config, security
│   │   ├── database/        # DynamoDB, PostgreSQL
│   │   ├── models/          # Pydantic models
│   │   └── services/        # Business logic
│   └── tests/
│       ├── unit/            # Unit tests
│       ├── integration/     # Integration tests
│       ├── regression/      # Critical path tests
│       └── fixtures/        # Test data
├── frontend-pwa/            # React frontend
├── infrastructure/          # Terraform configs
├── scripts/                 # Automation scripts
└── docs/                    # Documentation
```

---

## Environment Variables

### Required for Local Development
```bash
VYAPAARAI_ENV=development
AWS_REGION=ap-south-1
DYNAMODB_ENDPOINT=http://localhost:8000
POSTGRES_HOST=localhost
REDIS_HOST=localhost
```

### Start Local Services
```bash
docker-compose up -d
```

---

## DynamoDB Tables

| Table | Purpose |
|-------|---------|
| vyaparai-orders-{env} | Order processing |
| vyaparai-stores-{env} | Store master data |
| vyaparai-products-{env} | Product catalog |
| vyaparai-sessions-{env} | User sessions |
| vyaparai-metrics-{env} | Analytics |
| vyaparai-khata-transactions-{env} | Credit ledger |
| vyaparai-customer-balances-{env} | Balance cache |

---

## Quick Commands

```bash
# Start development
docker-compose up -d
cd backend && uvicorn app.main:app --reload

# Run tests
./scripts/run_tests.sh unit
./scripts/run_tests.sh coverage

# Create feature
./scripts/new_feature.sh my-feature

# Complete feature
./scripts/finish_feature.sh

# Deploy
./scripts/pre_deploy_check.sh
./scripts/release.sh 1.0.0
```
