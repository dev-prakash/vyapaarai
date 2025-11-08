#!/bin/bash

# Simple DynamoDB monitoring script
# Shows store registration in real-time

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

clear
echo -e "${BLUE}=== VyaparAI DynamoDB Monitor ===${NC}"
echo "Press Ctrl+C to exit"
echo ""

while true; do
    # Get counts
    STORES=$(aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 --select COUNT --output text --query Count 2>/dev/null)
    ORDERS=$(aws dynamodb scan --table-name vyaparai-orders-prod --region ap-south-1 --select COUNT --output text --query Count 2>/dev/null)
    
    # Clear and update display
    printf "\r${YELLOW}Stores:${NC} ${GREEN}$STORES${NC}  ${YELLOW}Orders:${NC} ${GREEN}$ORDERS${NC}  "
    
    # If stores exist, show latest
    if [ "$STORES" -gt "0" ]; then
        LATEST=$(aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 --output json 2>/dev/null | jq -r '.Items[-1] | "\(.store_name.S // .name.S)"' 2>/dev/null)
        printf "${YELLOW}Latest:${NC} ${GREEN}$LATEST${NC}  "
    fi
    
    sleep 2
done