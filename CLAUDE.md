# VyapaarAI - Claude Code Instructions

## WORKFLOW TRIGGERS (Read First!)

When a user prompt starts with these keywords, IMMEDIATELY read `WORKFLOWS.md` and execute the corresponding workflow:

| Trigger | Action |
|---------|--------|
| `Bug:` | Read WORKFLOWS.md → Execute "WORKFLOW: Bug Fix" |
| `Feature:` | Read WORKFLOWS.md → Execute "WORKFLOW: New Feature" |
| `Refactor:` | Read WORKFLOWS.md → Execute "WORKFLOW: Refactor" |
| `Hotfix:` | Read WORKFLOWS.md → Execute "WORKFLOW: Hotfix" |

### Examples
```
Bug: Store registration allows invalid phone numbers with less than 10 digits
```
→ Claude Code reads WORKFLOWS.md and executes full bug fix workflow automatically.

```
Feature: Add SMS notification when customer credit exceeds 80% of limit
```
→ Claude Code reads WORKFLOWS.md and executes full feature workflow automatically.

### What Happens Automatically

1. Creates appropriate branch (fix/, feature/, etc.)
2. Implements enterprise-grade code
3. Tests via Chrome MCP (if applicable)
4. Commits with proper message format
5. Generates regression/unit tests
6. Verifies all tests pass
7. Merges to develop
8. Updates documentation
9. Generates summary report

### Critical Rule

**ALWAYS ask for user confirmation** before:
- Starting implementation (after showing the plan)
- Merging to develop
- Any destructive operations

---

## Project Configuration

### Developer: DevPrakash

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

### Deployment
| Command | Description |
|---------|-------------|
| `/deploy backend` | Deploy backend (Lambda) with tests |
| `/deploy frontend` | Deploy frontend (S3 + CloudFront) |
| `/deploy all` | Full stack deployment |
| `/deploy lambda` | Quick Lambda update (skip tests option) |
| `/deploy status` | Show deployment status |
| `/deploy rollback` | Rollback to previous version |

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

### Test Type Disclosure (MANDATORY)

**ALWAYS tell the user what type of test is being created:**

| Type | Description | When to Use |
|------|-------------|-------------|
| **🔴 LIVE** | Hits production API/database | Critical user flows, deployment verification |
| **🟡 MOCK** | Uses MagicMock/AsyncMock | Expensive operations, destructive tests, unit logic |
| **🟢 STATIC** | AST/code analysis | Syntax validation, config checks (pre-deploy) |

**Example disclosure:**
```
Creating 3 tests:
- test_delete_product_permanently_removes → 🔴 LIVE (hits production API)
- test_archive_toggle_logic → 🟡 MOCK (unit test with mocks)
- test_endpoint_has_hard_delete_param → 🟢 STATIC (AST analysis)
```

**Decision criteria:**
- Use 🔴 LIVE for: Authentication, CRUD operations, API contracts
- Use 🟡 MOCK for: Complex business logic, edge cases, error handling
- Use 🟢 STATIC for: Syntax errors, missing endpoints, config issues

### Markers
- `@pytest.mark.unit` - Fast isolated tests (mock-based)
- `@pytest.mark.regression` - Critical path tests (MUST pass before deploy)
- `@pytest.mark.live` - Tests that hit production API/database
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

---

## Auto-Test Slash Commands

### /auto-test
Analyze recent commits and prepare for test generation.

**Execution:**
```bash
./scripts/auto_test.sh
```

**What it does:**
1. Identifies changed Python files from last commit
2. Detects change type (fix/feature/refactor) from commit message
3. Checks which files have existing tests
4. Saves analysis to /tmp/vyapaarai_auto_test/
5. Recommends test markers to use

---

### /generate-tests-from-analysis
Generate tests based on the /auto-test analysis.

**Prerequisites:** Run /auto-test first

**Execution steps:**

1. Read analysis files:
```bash
CHANGE_TYPE=$(cat /tmp/vyapaarai_auto_test/change_type.txt)
COMMIT_MSG=$(cat /tmp/vyapaarai_auto_test/commit_msg.txt)
cat /tmp/vyapaarai_auto_test/changed_files.txt
cat /tmp/vyapaarai_auto_test/files_without_tests.txt
```

2. For each file that needs tests:
   - Read the source file: `cat <filepath>`
   - Identify all functions, classes, DynamoDB operations
   - Generate appropriate tests based on CHANGE_TYPE

3. Apply markers based on CHANGE_TYPE:
   - "fix" → ALL tests get `@pytest.mark.regression`
   - "feature" → Mix of `@pytest.mark.unit` and `@pytest.mark.regression`
   - "refactor" → Primarily `@pytest.mark.unit`

4. Save tests to: `backend/tests/unit/test_<module>.py`

5. Run tests to verify: `pytest backend/tests/unit/test_<module>.py -v`

---

### /test-file <filepath>
Generate tests for a specific file (ignores recent commits).

**Execution:**
1. Read the file: `cat <filepath>`
2. Analyze all functions, classes, and logic
3. Generate comprehensive tests (happy path, edge cases, errors)
4. Mark critical business logic with `@pytest.mark.regression`
5. Save to `backend/tests/unit/test_<module>.py`
6. Run tests to verify

---

## Test Generation Rules

### ALWAYS:
- Author: DevPrakash (never mention AI/Claude)
- Use fixtures from conftest.py (dynamodb_mock, sample_store, etc.)
- Run tests after generating to verify they pass

### Markers by Change Type:
| Change Type | Commit Prefix | Test Markers |
|-------------|---------------|--------------|
| Bug Fix | `fix:` | ALL `@pytest.mark.regression` |
| Feature | `feat:` | Mix of `unit` and `regression` |
| Refactor | `refactor:` | Primarily `unit` |

### Test Naming Convention:
```
test_<function>_<scenario>_<expected_result>
```

Examples:
- `test_register_store_with_valid_data_succeeds`
- `test_register_store_with_missing_phone_fails`
- `test_cancel_order_restores_inventory`
