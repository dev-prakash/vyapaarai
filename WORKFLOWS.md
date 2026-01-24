# VyapaarAI Automated Development Workflows

## Overview

This document defines automated workflows for Claude Code. When a prompt starts with specific keywords, Claude Code executes the complete workflow automatically.

---

## Trigger Keywords

| Keyword | Workflow | Example |
|---------|----------|---------|
| `Bug:` | Full bug fix workflow | `Bug: Store registration allows invalid phone numbers` |
| `Feature:` | Full new feature workflow | `Feature: Add customer credit limit alerts` |
| `Refactor:` | Code refactoring workflow | `Refactor: Extract validation logic from stores.py` |
| `Hotfix:` | Emergency production fix | `Hotfix: Payment processing fails for amounts > 10000` |

---

## WORKFLOW: Bug Fix

### Trigger
Prompt starts with `Bug:` followed by bug description.

### Example
```
Bug: Store registration allows phone numbers with less than 10 digits
```

### Execution Steps

#### Phase 1: Setup
```
STEP 1.1: Parse bug description
- Extract: bug_summary (short, for branch name)
- Extract: bug_details (full description)

STEP 1.2: Create fix branch
```
```bash
git checkout develop
git pull origin develop
BRANCH_NAME="fix/$(echo '<bug_summary>' | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | cut -c1-50)"
git checkout -b "$BRANCH_NAME"
```
```
STEP 1.3: Announce plan
- State which files likely need changes
- State the approach to fix
- Ask: "Proceed with this plan? (yes/no)"
- Wait for user confirmation before proceeding
```

#### Phase 2: Implement Fix
```
STEP 2.1: Locate relevant code
- Search codebase for related files
- Read and understand current implementation

STEP 2.2: Implement fix
- Apply enterprise-grade coding practices:
  • Input validation
  • Error handling with specific exceptions
  • Logging for debugging
  • Type hints
  • Docstrings
- Make minimal, focused changes
- Don't refactor unrelated code

STEP 2.3: Commit fix
```
```bash
git add -A
git commit -m "fix: <concise description of fix>"
```

#### Phase 3: Browser Testing (if applicable)
```
STEP 3.1: Determine if browser testing needed
- API endpoints → Yes, test via browser
- Utility functions → No, skip to Phase 4
- Database operations → No, skip to Phase 4

STEP 3.2: Browser testing (using Chrome MCP)
- Navigate to relevant page/endpoint
- Test the fixed functionality
- Verify fix works correctly
- Take screenshot as evidence
- Report: "Browser test PASSED" or "Browser test FAILED: <reason>"

STEP 3.3: If browser test fails
- Analyze failure
- Return to Phase 2 to refine fix
- Repeat until browser test passes
```

#### Phase 4: Generate Regression Tests
```
STEP 4.1: Generate tests
- Create test file: backend/tests/unit/test_<module>.py (or update existing)
- ALL tests marked with @pytest.mark.regression
- Include test that reproduces original bug scenario
- Include edge cases around the fix
- Use fixtures from conftest.py

STEP 4.2: Test structure
```
```python
"""
Regression tests for <module>
Bug fix: <bug_description>
Author: DevPrakash
"""
import pytest

class Test<BugFix>Regression:
    """Regression tests preventing bug recurrence"""

    @pytest.mark.regression
    def test_<bug_scenario>_now_works_correctly(self, dynamodb_mock):
        """
        REGRESSION: <bug_description>

        Original bug: <what was broken>
        Fix: <what was changed>
        """
        # Test implementation
        pass

    @pytest.mark.regression
    def test_<edge_case>_handled(self, dynamodb_mock):
        """Edge case around the bug fix"""
        pass
```

#### Phase 5: Verify Tests Pass
```
STEP 5.1: Run new tests
```
```bash
pytest backend/tests/unit/test_<module>.py -v -m regression
```
```
STEP 5.2: If tests fail
- Analyze failure
- Fix test or code as needed
- Re-run until all pass

STEP 5.3: Run full regression suite (on new file only)
```
```bash
pytest backend/tests/unit/test_<module>.py -v
```

#### Phase 6: Commit Tests
```
STEP 6.1: Commit tests
```
```bash
git add backend/tests/
git commit -m "test: add regression tests for <bug_summary>"
```

#### Phase 7: Merge to Develop
```
STEP 7.1: Merge
```
```bash
git checkout develop
git merge --no-ff "$BRANCH_NAME" -m "Merge $BRANCH_NAME into develop"
```
```
STEP 7.2: Push
```
```bash
git push origin develop
```
```
STEP 7.3: Cleanup (optional)
```
```bash
git branch -d "$BRANCH_NAME"
```

#### Phase 8: Documentation
```
STEP 8.1: Update CHANGELOG.md (create if not exists)
- Add entry under "## [Unreleased]"
- Format: `- **Fixed:** <bug_description>`

STEP 8.2: Generate summary report
```
```markdown
## Bug Fix Complete ✅

### Summary
- **Bug:** <original bug description>
- **Branch:** <branch_name>
- **Files Modified:** <list>
- **Tests Added:** <count> regression tests
- **Status:** Merged to develop

### What Was Fixed
<Technical explanation>

### How to Verify
<Steps to manually verify the fix>

### Commits
1. `<hash>` - fix: <message>
2. `<hash>` - test: <message>
```

---

## WORKFLOW: New Feature

### Trigger
Prompt starts with `Feature:` followed by feature description.

### Example
```
Feature: Add customer credit limit alerts when balance exceeds 80%
```

### Execution Steps

#### Phase 1: Setup
```
STEP 1.1: Parse feature description
- Extract: feature_summary (short, for branch name)
- Extract: feature_details (full description)
- Extract: acceptance_criteria (if mentioned)

STEP 1.2: Create feature branch
```
```bash
git checkout develop
git pull origin develop
BRANCH_NAME="feature/$(echo '<feature_summary>' | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | cut -c1-50)"
git checkout -b "$BRANCH_NAME"
```
```
STEP 1.3: Create implementation plan
- List all components needed:
  • API endpoints
  • Database changes
  • Service layer logic
  • Validation rules
  • UI changes (if any)
- Ask: "Proceed with this plan? (yes/no)"
- Wait for user confirmation before proceeding
```

#### Phase 2: Implement Feature
```
STEP 2.1: Database/Model layer (if needed)
- Add new models or fields
- Follow existing patterns in codebase
- Add proper indexes

STEP 2.2: Service layer
- Implement business logic
- Enterprise-grade practices:
  • Input validation
  • Error handling
  • Logging
  • Type hints
  • Docstrings
  • Async where appropriate

STEP 2.3: API layer
- Add endpoints following existing patterns
- Proper request/response models
- Authentication/authorization
- Rate limiting considerations

STEP 2.4: Commit incrementally
```
```bash
git add -A
git commit -m "feat: add <component> for <feature>"
```
```
- Commit after each logical component
```

#### Phase 3: Browser Testing
```
STEP 3.1: Test via Chrome MCP
- Navigate to relevant pages
- Test all new functionality
- Test edge cases
- Take screenshots as evidence

STEP 3.2: Verify all acceptance criteria met
- Check each criterion
- Report status of each

STEP 3.3: If any test fails
- Fix and re-test
- Repeat until all pass
```

#### Phase 4: Generate Tests
```
STEP 4.1: Generate comprehensive tests
- Create: backend/tests/unit/test_<feature>.py
- Include:
  • Happy path tests (@pytest.mark.unit)
  • Edge case tests (@pytest.mark.unit)
  • Error handling tests (@pytest.mark.unit)
  • Critical business logic (@pytest.mark.regression)

STEP 4.2: Test coverage targets
- All public functions tested
- All API endpoints tested
- All validation rules tested
- All error conditions tested
```

#### Phase 5: Verify Tests Pass
```
STEP 5.1: Run all new tests
```
```bash
pytest backend/tests/unit/test_<feature>.py -v
```
```
STEP 5.2: Verify regression tests pass
```
```bash
pytest backend/tests/unit/test_<feature>.py -v -m regression
```

#### Phase 6: Commit Tests
```
STEP 6.1: Commit
```
```bash
git add backend/tests/
git commit -m "test: add comprehensive tests for <feature>"
```

#### Phase 7: Documentation
```
STEP 7.1: Update API documentation (if API changes)
- Add to docs/api/ or inline docstrings
- Include request/response examples

STEP 7.2: Update README or relevant docs
- If user-facing feature, document usage

STEP 7.3: Update CHANGELOG.md
- Add under "## [Unreleased]"
- Format: `- **Added:** <feature_description>`
```

#### Phase 8: Merge
```
STEP 8.1: Final verification
```
```bash
pytest backend/tests/unit/test_<feature>.py -v
```
```
STEP 8.2: Merge to develop
```
```bash
git checkout develop
git merge --no-ff "$BRANCH_NAME" -m "Merge $BRANCH_NAME into develop"
git push origin develop
```
```
STEP 8.3: Generate summary report
```
```markdown
## Feature Complete ✅

### Summary
- **Feature:** <description>
- **Branch:** <branch_name>
- **Files Created:** <list>
- **Files Modified:** <list>
- **Tests Added:** <count> total (<unit> unit, <regression> regression)
- **Status:** Merged to develop

### What Was Added
<Technical explanation of the feature>

### API Endpoints (if any)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/... | ... |

### How to Use
<User documentation>

### Commits
1. `<hash>` - feat: <message>
2. `<hash>` - feat: <message>
3. `<hash>` - test: <message>
```

---

## WORKFLOW: Refactor

### Trigger
Prompt starts with `Refactor:` followed by description.

### Example
```
Refactor: Extract validation logic from stores.py into separate validators module
```

### Key Differences from Feature
- Branch prefix: `refactor/`
- Commit prefix: `refactor:`
- NO behavior changes (existing tests must still pass)
- Run existing tests before AND after changes
- Tests focus on verifying behavior unchanged

### Execution Steps

#### Phase 1: Setup
```
STEP 1.1: Create refactor branch
```
```bash
git checkout develop
git pull origin develop
BRANCH_NAME="refactor/$(echo '<description>' | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | cut -c1-50)"
git checkout -b "$BRANCH_NAME"
```

#### Phase 2: Pre-Refactor Verification
```
STEP 2.1: Run existing tests
```
```bash
pytest backend/tests/ -v --tb=short
```
```
STEP 2.2: Document current behavior
- Note all public interfaces
- Note all return types
- Note all side effects
```

#### Phase 3: Implement Refactor
```
STEP 3.1: Apply changes
- Restructure code as needed
- Maintain ALL existing behavior
- Update imports as needed
- Keep public interfaces stable

STEP 3.2: Commit incrementally
```
```bash
git add -A
git commit -m "refactor: <description of change>"
```

#### Phase 4: Post-Refactor Verification
```
STEP 4.1: Run ALL existing tests
```
```bash
pytest backend/tests/ -v --tb=short
```
```
STEP 4.2: Verify no behavior changes
- All tests must pass
- No new failures allowed
```

#### Phase 5: Merge
```
STEP 5.1: Merge to develop
```
```bash
git checkout develop
git merge --no-ff "$BRANCH_NAME" -m "Merge $BRANCH_NAME into develop"
git push origin develop
```

---

## WORKFLOW: Hotfix

### Trigger
Prompt starts with `Hotfix:` followed by critical bug description.

### Example
```
Hotfix: Payment processing fails for amounts greater than 10000
```

### Key Differences from Bug Fix
- Branch from `main` (not develop)
- Merge to BOTH `main` AND `develop`
- Minimal changes only
- Immediate deployment after merge

### Execution Steps

#### Phase 1: Setup
```
STEP 1.1: Branch from main
```
```bash
git checkout main
git pull origin main
git checkout -b "hotfix/<description>"
```

#### Phase 2: Fix (Minimal Changes Only)
```
STEP 2.1: Implement fix
- Absolute minimum changes
- No refactoring
- No unrelated changes
- Focus only on the critical issue

STEP 2.2: Commit
```
```bash
git add -A
git commit -m "fix: <critical fix description>"
```

#### Phase 3: Test
```
STEP 3.1: Run regression tests
```
```bash
pytest backend/tests/ -v -m regression
```
```
STEP 3.2: Manual verification
- Test the specific fix
- Verify no regressions
```

#### Phase 4: Merge to Main AND Develop
```
STEP 4.1: Merge to main
```
```bash
git checkout main
git merge --no-ff "hotfix/<description>" -m "Hotfix: <description>"
git tag -a v<version> -m "Hotfix: <description>"
git push origin main --tags
```
```
STEP 4.2: Merge to develop
```
```bash
git checkout develop
git merge --no-ff "hotfix/<description>" -m "Merge hotfix/<description> into develop"
git push origin develop
```
```
STEP 4.3: Cleanup
```
```bash
git branch -d "hotfix/<description>"
```

#### Phase 5: Deployment
```
STEP 5.1: Deploy to production immediately
- Follow deployment checklist
- Monitor for issues
- Be ready to rollback if needed
```

---

## Enterprise Code Standards

### All Code Must Include:

1. **Type Hints**
```python
def calculate_balance(customer_id: str, store_id: str) -> Decimal:
```

2. **Docstrings**
```python
def calculate_balance(customer_id: str, store_id: str) -> Decimal:
    """
    Calculate customer's current balance for a store.

    Args:
        customer_id: Unique customer identifier
        store_id: Store identifier

    Returns:
        Current balance as Decimal

    Raises:
        CustomerNotFoundError: If customer doesn't exist
        StoreNotFoundError: If store doesn't exist
    """
```

3. **Input Validation**
```python
if not customer_id or not customer_id.strip():
    raise ValueError("customer_id is required")
```

4. **Error Handling**
```python
try:
    result = await db.get_item(...)
except ClientError as e:
    logger.error(f"DynamoDB error: {e}")
    raise DatabaseError("Failed to fetch customer") from e
```

5. **Logging**
```python
logger.info(f"Calculating balance for customer {customer_id}")
logger.debug(f"Found {len(transactions)} transactions")
```

---

## Test Standards

### Naming Convention
```
test_<function>_<scenario>_<expected_result>
```

### Required Markers
- `@pytest.mark.unit` - Fast, isolated tests
- `@pytest.mark.regression` - Critical business logic (must pass before deploy)
- `@pytest.mark.integration` - Tests with external dependencies
- `@pytest.mark.slow` - Long-running tests

### Test Structure
```python
def test_function_scenario_expected_result(self, fixture):
    # Arrange
    input_data = {...}

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected_value
```

### Test File Organization
```
backend/tests/
├── conftest.py          # Shared fixtures
├── unit/                # Unit tests
│   ├── test_stores.py
│   ├── test_orders.py
│   └── test_<module>.py
├── integration/         # Integration tests
├── regression/          # Regression test suites
└── fixtures/            # Test data
```

---

## Browser Testing Standards (Chrome MCP)

### When to Use Browser Testing
- API endpoints that affect UI
- User-facing functionality
- End-to-end flows
- Visual verification needed

### How to Test
1. Navigate to the page/endpoint
2. Perform the action
3. Verify the result
4. Take screenshot for evidence
5. Report pass/fail with details

### Example Browser Test Flow
```
1. mcp__chrome-devtools__navigate_page(url="https://www.vyapaarai.com/stores")
2. mcp__chrome-devtools__take_snapshot()
3. mcp__chrome-devtools__fill(uid="...", value="test data")
4. mcp__chrome-devtools__click(uid="...")
5. mcp__chrome-devtools__wait_for(text="Success")
6. mcp__chrome-devtools__take_screenshot()
```

---

## Documentation Standards

### CHANGELOG.md Format
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New feature descriptions

### Fixed
- Bug fix descriptions

### Changed
- Modification descriptions

### Removed
- Removed feature descriptions

## [1.0.0] - 2025-01-24

### Added
- Initial release features
```

### API Documentation
- Include in docstrings or docs/api/
- Show request/response examples
- Document all parameters
- Document error responses

---

## Git Standards

### Commit Message Format
```
<type>: <concise description>

<optional body with details>
```

### Types
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code restructure (no behavior change)
- `test:` - Adding or updating tests
- `docs:` - Documentation only
- `chore:` - Maintenance tasks
- `perf:` - Performance improvement
- `style:` - Code style changes (formatting, etc.)

### Branch Naming
- `feature/<short-description>`
- `fix/<short-description>`
- `refactor/<short-description>`
- `hotfix/<short-description>`

### Merge Strategy
- Always use `--no-ff` for merges to preserve branch history
- Squash commits only for very small changes
- Keep meaningful commit history

---

## Critical Rules

1. **NEVER mention AI/Claude** in code, comments, commits, or documentation
2. **Author**: All work attributed to DevPrakash
3. **Ask before proceeding** at key decision points (Phase 1 of each workflow)
4. **Test before merging** - No untested code in develop
5. **Regression tests for ALL bug fixes** - Prevent recurrence
6. **Minimal changes** - Don't refactor unrelated code during fixes
7. **Incremental commits** - Commit after each logical unit of work
8. **Documentation updates** - Keep docs in sync with code changes

---

## Quick Reference

### Start a Bug Fix
```
Bug: <description of the bug>
```

### Start a Feature
```
Feature: <description of the feature>
```

### Start a Refactor
```
Refactor: <description of the refactoring>
```

### Emergency Hotfix
```
Hotfix: <description of critical issue>
```

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-01-24 | DevPrakash | Initial workflow definitions |
