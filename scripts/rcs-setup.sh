#!/bin/bash
set -e

echo "🚀 Setting up Google RCS Business Messaging for VyaparAI"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
RCS_AGENT_ID=${RCS_AGENT_ID:-"vyaparai-agent"}
GOOGLE_CLOUD_PROJECT_ID=${GOOGLE_CLOUD_PROJECT_ID:-"vyaparai-project"}
RCS_WEBHOOK_URL=${RCS_WEBHOOK_URL:-"https://api.vyaparai.com/api/v1/webhooks/rcs"}
STAGE=${STAGE:-"dev"}

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI not found. Please install Google Cloud SDK:"
        echo "https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        print_error "jq not found. Please install jq for JSON processing:"
        echo "brew install jq  # macOS"
        echo "apt-get install jq  # Ubuntu/Debian"
        exit 1
    fi
    
    # Check if service account file exists
    if [ ! -f "rcs-service-account.json" ]; then
        print_warning "Missing rcs-service-account.json"
        echo "Please download from Google Cloud Console:"
        echo "1. Go to https://console.cloud.google.com"
        echo "2. Navigate to IAM & Admin > Service Accounts"
        echo "3. Create service account with RCS Business Messaging API"
        echo "4. Download JSON key as rcs-service-account.json"
        echo ""
        echo "Or set RCS_SERVICE_ACCOUNT_PATH environment variable"
        exit 1
    fi
    
    print_status "Prerequisites check passed"
}

# Authenticate with Google Cloud
authenticate_gcloud() {
    print_info "Authenticating with Google Cloud..."
    
    # Check if already authenticated
    if gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        print_status "Already authenticated with Google Cloud"
    else
        print_info "Please authenticate with Google Cloud..."
        gcloud auth login
    fi
    
    # Set project
    gcloud config set project $GOOGLE_CLOUD_PROJECT_ID
    
    print_status "Google Cloud authentication complete"
}

# Enable required APIs
enable_apis() {
    print_info "Enabling required APIs..."
    
    # Enable RCS Business Messaging API
    gcloud services enable rcsbusinessmessaging.googleapis.com
    
    # Enable Business Communications API
    gcloud services enable businesscommunications.googleapis.com
    
    # Enable Cloud Build API (for deployment)
    gcloud services enable cloudbuild.googleapis.com
    
    print_status "APIs enabled successfully"
}

# Create RCS agent configuration
create_agent_config() {
    print_info "Creating RCS agent configuration..."
    
    cat > rcs-agent-config.json <<EOF
{
  "displayName": "VyaparAI Store",
  "businessMessagingAgent": {
    "displayName": "VyaparAI",
    "logo": {
      "sourceUrl": "https://vyaparai.com/logo.png"
    },
    "customAgentId": "${RCS_AGENT_ID}",
    "verificationConfig": {
      "agentVerificationContact": {
        "partnerName": "VyaparAI",
        "partnerEmailAddress": "support@vyaparai.com",
        "brandContactEmailAddress": "contact@vyaparai.com"
      }
    },
    "nonLocalConfig": {
      "enabledRegions": ["IN"],
      "contactOption": "EMAIL",
      "phoneNumbers": ["+919876543210"],
      "callDeflectionPhoneNumbers": ["+919876543210"],
      "enableWelcomeMessage": true,
      "welcomeMessage": {
        "text": "Welcome to VyaparAI! Send your grocery order in any language."
      }
    },
    "conversationalSettings": {
      "en": {
        "welcomeMessage": {
          "text": "Welcome! Order groceries in any language."
        },
        "privacyPolicy": {
          "url": "https://vyaparai.com/privacy"
        }
      },
      "hi": {
        "welcomeMessage": {
          "text": "स्वागत है! किसी भी भाषा में किराने का सामान ऑर्डर करें।"
        }
      },
      "ta": {
        "welcomeMessage": {
          "text": "வரவேற்கிறோம்! எந்த மொழியிலும் கடை பொருட்களை ஆர்டர் செய்யுங்கள்."
        }
      },
      "bn": {
        "welcomeMessage": {
          "text": "স্বাগতম! যেকোনো ভাষায় মুদি সামগ্রী অর্ডার করুন।"
        }
      },
      "te": {
        "welcomeMessage": {
          "text": "స్వాగతం! ఏ భాషలోనైనా కిరాణా వస్తువులు ఆర్డర్ చేయండి."
        }
      }
    }
  }
}
EOF

    print_status "RCS agent configuration created"
}

# Register webhook with Google RCS
register_webhook() {
    print_info "Registering webhook with Google RCS..."
    
    # Get access token
    ACCESS_TOKEN=$(gcloud auth print-access-token)
    
    # Register webhook
    WEBHOOK_RESPONSE=$(curl -s -X POST \
        "https://rcsbusinessmessaging.googleapis.com/v1/phones/agentWebhookConfig" \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"agentId\": \"${RCS_AGENT_ID}\",
            \"webhookUri\": \"${RCS_WEBHOOK_URL}\"
        }")
    
    if echo "$WEBHOOK_RESPONSE" | jq -e '.name' > /dev/null; then
        print_status "Webhook registered successfully"
        echo "$WEBHOOK_RESPONSE" | jq '.'
    else
        print_error "Failed to register webhook"
        echo "$WEBHOOK_RESPONSE"
        exit 1
    fi
}

# Add test numbers
add_test_numbers() {
    print_info "Setting up test numbers..."
    
    # Test numbers (replace with actual test numbers)
    TEST_NUMBERS=("+919999999999" "+918888888888" "+917777777777")
    
    ACCESS_TOKEN=$(gcloud auth print-access-token)
    
    for number in "${TEST_NUMBERS[@]}"; do
        print_info "Adding test number: $number"
        
        RESPONSE=$(curl -s -X POST \
            "https://rcsbusinessmessaging.googleapis.com/v1/phones/$number/testers" \
            -H "Authorization: Bearer $ACCESS_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"agentId\": \"${RCS_AGENT_ID}\"}")
        
        if echo "$RESPONSE" | jq -e '.name' > /dev/null; then
            print_status "Test number $number added successfully"
        else
            print_warning "Failed to add test number $number"
            echo "$RESPONSE"
        fi
    done
}

# Create environment configuration
create_env_config() {
    print_info "Creating environment configuration..."
    
    cat > .env.rcs <<EOF
# RCS Configuration
RCS_AGENT_ID=${RCS_AGENT_ID}
GOOGLE_CLOUD_PROJECT_ID=${GOOGLE_CLOUD_PROJECT_ID}
RCS_SERVICE_ACCOUNT_PATH=rcs-service-account.json
RCS_WEBHOOK_URL=${RCS_WEBHOOK_URL}

# Stage-specific configuration
STAGE=${STAGE}
ENVIRONMENT=${STAGE}

# API Configuration
API_BASE_URL=https://api.vyaparai.com
WEBHOOK_SECRET=your_webhook_secret_here

# Test Configuration
TEST_PHONE_NUMBERS=+919999999999,+918888888888,+917777777777
EOF

    print_status "Environment configuration created (.env.rcs)"
}

# Test RCS messaging
test_rcs_messaging() {
    print_info "Testing RCS messaging..."
    
    # Create test script
    cat > test_rcs_message.py <<EOF
#!/usr/bin/env python3
"""
Test RCS messaging functionality
"""

import asyncio
import httpx
import json
import os
from google.oauth2 import service_account
from google.auth.transport.requests import Request

async def test_rcs_message():
    """Test sending RCS message"""
    
    # Load credentials
    creds = service_account.Credentials.from_service_account_file(
        'rcs-service-account.json',
        scopes=['https://www.googleapis.com/auth/rcsbusinessmessaging']
    )
    creds.refresh(Request())
    
    # Test message
    url = "https://rcsbusinessmessaging.googleapis.com/v1/phones/+919999999999/agentMessages"
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json"
    }
    
    message = {
        "contentMessage": {
            "text": "🎉 RCS is working! Welcome to VyaparAI.",
            "suggestions": [
                {
                    "reply": {
                        "text": "Test Order",
                        "postbackData": "action=test"
                    }
                },
                {
                    "reply": {
                        "text": "Browse Products",
                        "postbackData": "action=browse"
                    }
                }
            ]
        },
        "agentId": "${RCS_AGENT_ID}",
        "messageId": "test-message-$(int(time.time()))",
        "msisdn": "919999999999"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=message)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Test message sent successfully: {result.get('name', 'unknown')}")
            return True
        else:
            print(f"❌ Test message failed: {response.status_code} - {response.text}")
            return False

if __name__ == "__main__":
    import time
    asyncio.run(test_rcs_message())
EOF

    # Run test
    if python3 test_rcs_message.py; then
        print_status "RCS messaging test passed"
    else
        print_warning "RCS messaging test failed"
    fi
    
    # Cleanup
    rm -f test_rcs_message.py
}

# Create deployment script
create_deployment_script() {
    print_info "Creating deployment script..."
    
    cat > deploy-rcs.sh <<EOF
#!/bin/bash
set -e

echo "🚀 Deploying RCS integration to ${STAGE}..."

# Load environment variables
source .env.rcs

# Deploy to AWS Lambda (if using serverless)
if command -v serverless &> /dev/null; then
    echo "Deploying with Serverless Framework..."
    serverless deploy --stage ${STAGE}
else
    echo "Serverless Framework not found. Please deploy manually."
fi

# Update webhook URL if needed
if [ "\$STAGE" != "prod" ]; then
    echo "Updating webhook URL for ${STAGE}..."
    ACCESS_TOKEN=\$(gcloud auth print-access-token)
    
    curl -X POST \\
        "https://rcsbusinessmessaging.googleapis.com/v1/phones/agentWebhookConfig" \\
        -H "Authorization: Bearer \$ACCESS_TOKEN" \\
        -H "Content-Type: application/json" \\
        -d "{
            \\"agentId\\": \\"\${RCS_AGENT_ID}\\",
            \\"webhookUri\\": \\"\${RCS_WEBHOOK_URL}\\"
        }"
fi

echo "✅ RCS deployment complete!"
EOF

    chmod +x deploy-rcs.sh
    print_status "Deployment script created (deploy-rcs.sh)"
}

# Create monitoring script
create_monitoring_script() {
    print_info "Creating monitoring script..."
    
    cat > monitor-rcs.sh <<EOF
#!/bin/bash

echo "📊 RCS Integration Monitoring"

# Check webhook health
echo "Checking webhook health..."
curl -s "\${RCS_WEBHOOK_URL}/health" | jq '.'

# Check agent status
echo "Checking agent status..."
ACCESS_TOKEN=\$(gcloud auth print-access-token)
curl -s \\
    "https://rcsbusinessmessaging.googleapis.com/v1/agents/\${RCS_AGENT_ID}" \\
    -H "Authorization: Bearer \$ACCESS_TOKEN" | jq '.'

# Check recent messages (if any)
echo "Checking recent activity..."
curl -s \\
    "https://rcsbusinessmessaging.googleapis.com/v1/phones/+919999999999/agentMessages" \\
    -H "Authorization: Bearer \$ACCESS_TOKEN" | jq '.agentMessages[] | {messageId, timestamp, contentMessage}' | head -10
EOF

    chmod +x monitor-rcs.sh
    print_status "Monitoring script created (monitor-rcs.sh)"
}

# Main setup function
main() {
    echo "🚀 VyaparAI RCS Business Messaging Setup"
    echo "========================================"
    echo "Agent ID: $RCS_AGENT_ID"
    echo "Project ID: $GOOGLE_CLOUD_PROJECT_ID"
    echo "Webhook URL: $RCS_WEBHOOK_URL"
    echo "Stage: $STAGE"
    echo ""
    
    # Run setup steps
    check_prerequisites
    authenticate_gcloud
    enable_apis
    create_agent_config
    register_webhook
    add_test_numbers
    create_env_config
    test_rcs_messaging
    create_deployment_script
    create_monitoring_script
    
    echo ""
    echo "🎉 RCS Setup Complete!"
    echo "======================"
    echo ""
    echo "Next steps:"
    echo "1. Review and update .env.rcs with your configuration"
    echo "2. Deploy your application: ./deploy-rcs.sh"
    echo "3. Verify agent at: https://business.messages.google.com/console"
    echo "4. Test with RCS-enabled Android phone"
    echo "5. Monitor integration: ./monitor-rcs.sh"
    echo ""
    echo "Test numbers configured:"
    echo "  - +919999999999"
    echo "  - +918888888888"
    echo "  - +917777777777"
    echo ""
    echo "Documentation:"
    echo "  - RCS Integration Guide: docs/RCS_INTEGRATION.md"
    echo "  - API Documentation: https://developers.google.com/business-communications/rcs-business-messaging"
    echo ""
}

# Run main function
main "$@"
