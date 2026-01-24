#!/bin/bash
#
# VyapaarAI Auto-Test Analyzer
# Developer: DevPrakash
#
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  VyapaarAI Auto-Test Analyzer${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

COMMITS=${1:-1}
ANALYSIS_DIR="/tmp/vyapaarai_auto_test"
mkdir -p "$ANALYSIS_DIR"

echo ""
echo -e "${CYAN}[1/5] Analyzing Last $COMMITS Commit(s)...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

git log -"$COMMITS" --format="  %C(yellow)%h%C(reset) %s %C(dim)(%ar)%C(reset)"

COMMIT_MSG=$(git log -1 --format="%s")
COMMIT_HASH=$(git log -1 --format="%h")

if echo "$COMMIT_MSG" | grep -qiE "^fix:|bugfix|hotfix"; then
    CHANGE_TYPE="fix"
elif echo "$COMMIT_MSG" | grep -qiE "^feat:|feature|^add:"; then
    CHANGE_TYPE="feature"
elif echo "$COMMIT_MSG" | grep -qiE "^refactor:"; then
    CHANGE_TYPE="refactor"
else
    CHANGE_TYPE="unknown"
fi

echo ""
echo -e "${YELLOW}Change Type:${NC} $CHANGE_TYPE"
echo -e "${YELLOW}Commit:${NC} $COMMIT_MSG"

echo "$CHANGE_TYPE" > "$ANALYSIS_DIR/change_type.txt"
echo "$COMMIT_MSG" > "$ANALYSIS_DIR/commit_msg.txt"
echo "$COMMIT_HASH" > "$ANALYSIS_DIR/commit_hash.txt"

echo ""
echo -e "${CYAN}[2/5] Finding Changed Files...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CHANGED_FILES=$(git diff-tree --no-commit-id --name-only -r HEAD~$((COMMITS-1))..HEAD 2>/dev/null | grep "\.py$" | grep -v "test_" | grep -v "__pycache__" || true)

if [ -z "$CHANGED_FILES" ]; then
    echo -e "${YELLOW}No Python source files changed.${NC}"
    exit 0
fi

echo "$CHANGED_FILES" > "$ANALYSIS_DIR/changed_files.txt"
echo -e "${GREEN}Changed files:${NC}"
echo "$CHANGED_FILES" | while read -r file; do
    [ -n "$file" ] && echo "  • $file"
done

echo ""
echo -e "${CYAN}[3/5] Checking Existing Tests...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

> "$ANALYSIS_DIR/files_with_tests.txt"
> "$ANALYSIS_DIR/files_without_tests.txt"

echo "$CHANGED_FILES" | while read -r file; do
    [ -z "$file" ] && continue
    module=$(basename "$file" .py)
    existing=$(find . -name "test_${module}.py" 2>/dev/null | grep -v __pycache__ | head -1)
    
    if [ -n "$existing" ]; then
        echo -e "  ${GREEN}✓${NC} $file → $existing"
        echo "$file|$existing" >> "$ANALYSIS_DIR/files_with_tests.txt"
    else
        echo -e "  ${RED}✗${NC} $file → No tests"
        echo "$file" >> "$ANALYSIS_DIR/files_without_tests.txt"
    fi
done

echo ""
echo -e "${CYAN}[4/5] Recommendations...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

case $CHANGE_TYPE in
    "fix")
        echo -e "  ${RED}●${NC} BUG FIX detected"
        echo "  → ALL tests should be @pytest.mark.regression"
        echo "regression" > "$ANALYSIS_DIR/recommended_marker.txt"
        ;;
    "feature")
        echo -e "  ${GREEN}●${NC} NEW FEATURE detected"
        echo "  → Mix of @pytest.mark.unit and @pytest.mark.regression"
        echo "mixed" > "$ANALYSIS_DIR/recommended_marker.txt"
        ;;
    "refactor")
        echo -e "  ${BLUE}●${NC} REFACTOR detected"
        echo "  → Primarily @pytest.mark.unit"
        echo "unit" > "$ANALYSIS_DIR/recommended_marker.txt"
        ;;
    *)
        echo -e "  ${YELLOW}●${NC} UNKNOWN change type"
        echo "unit" > "$ANALYSIS_DIR/recommended_marker.txt"
        ;;
esac

echo ""
echo -e "${CYAN}[5/5] Summary...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Files changed: $(echo "$CHANGED_FILES" | wc -l | tr -d ' ')"
echo "  Need tests: $(wc -l < "$ANALYSIS_DIR/files_without_tests.txt" | tr -d ' ')"
echo "  Have tests: $(wc -l < "$ANALYSIS_DIR/files_with_tests.txt" | tr -d ' ')"
echo ""
echo -e "${GREEN}Analysis saved to: $ANALYSIS_DIR${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}NEXT STEP:${NC} Send this to Claude Code:"
echo -e "${CYAN}  /generate-tests-from-analysis${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
