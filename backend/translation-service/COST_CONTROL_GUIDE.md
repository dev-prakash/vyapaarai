# 💰 Cost Control Guide - Translation Service

## 🎯 Problem Solved

**You asked:** "Is there a way I can create a switch to keep control on pricing?"

**Answer:** YES! You now have **4 operation modes** with complete cost control.

---

## 🔧 4 Operation Modes

### **Mode 1: DISABLED** (FREE - $0/month)
```bash
TRANSLATION_MODE=disabled
```
- Returns English text only
- No translations at all
- **Cost: $0 for translation** (only basic Lambda/DynamoDB: ~$3/month)
- **Use when:** Service not needed yet

---

### **Mode 2: MOCK** (FREE - $0/month for translation)
```bash
TRANSLATION_MODE=mock
```
- Returns fake/mock translations
- No Amazon Translate API calls
- Good for testing UI/frontend
- **Cost: $0 for translation** (only Lambda/DynamoDB: ~$3/month)
- **Use when:** Testing UI, developing frontend, demoing

**Example output:**
```json
{
  "productName": "टाटा नमक [MOCK]",
  "productDescription": "प्रीमियम आयोडीन युक्त नमक [MOCK]"
}
```

---

### **Mode 3: CACHE_ONLY** (Very Cheap - $1-2/month)
```bash
TRANSLATION_MODE=cache_only
```
- Only returns cached translations
- Never calls Amazon Translate API
- Returns English if translation not in cache
- **Cost: ~$1-2/month** (DynamoDB reads only)
- **Use when:** Testing with limited budget, using pre-translated products

---

### **Mode 4: FULL** (Normal - $40-60/month)
```bash
TRANSLATION_MODE=full
```
- Full translation service
- Calls Amazon Translate when needed
- Uses cache when available
- **Cost: ~$40-60/month** (based on usage)
- **Use when:** Production with real users

---

## 💡 Recommended Path for You

### **Phase 1: Build & Test (Week 1-2)**
Use: **MOCK mode**
```bash
TRANSLATION_MODE=mock
ENABLE_AMAZON_TRANSLATE=false
MAX_TRANSLATIONS_PER_DAY=100
MAX_DAILY_COST_USD=1.00
```
**Cost: $0/month for translation**

### **Phase 2: Internal Testing (Week 3-4)**
Use: **CACHE_ONLY mode**
```bash
TRANSLATION_MODE=cache_only
ENABLE_AMAZON_TRANSLATE=false
MAX_TRANSLATIONS_PER_DAY=500
MAX_DAILY_COST_USD=2.00
```
**Cost: ~$1-2/month**

Pre-populate cache with a one-time batch:
```bash
# One-time: Translate your 200 products
# Cost: ~$5 one-time fee
# Then switch to CACHE_ONLY forever
```

### **Phase 3: Limited Beta (Month 2)**
Use: **FULL mode with limits**
```bash
TRANSLATION_MODE=full
ENABLE_AMAZON_TRANSLATE=true
MAX_TRANSLATIONS_PER_DAY=1000
MAX_DAILY_COST_USD=5.00
ALLOWED_TEST_USERS=user1@email.com,user2@email.com
```
**Cost: ~$5/month** (limited users only)

### **Phase 4: Production Launch**
Use: **FULL mode**
```bash
TRANSLATION_MODE=full
MAX_TRANSLATIONS_PER_DAY=10000
MAX_DAILY_COST_USD=10.00
```
**Cost: $40-60/month** (scales with users)

---

## 🚦 Quick Start Configs

### **For Testing NOW (Free):**
```bash
# Use the .env.testing file
cp .env.testing .env

# Deploy with MOCK mode
TRANSLATION_MODE=mock
ENABLE_AMAZON_TRANSLATE=false
ALLOWED_TEST_USERS=your-email@example.com
ALLOWED_LANGUAGES=en,hi  # Only 2 languages
```

**Expected cost: $0/day for translation** ✅

---

### **For Development (Very Cheap):**
```bash
# Use the .env.development file
cp .env.development .env

# Deploy with CACHE_ONLY mode
TRANSLATION_MODE=cache_only
ENABLE_AMAZON_TRANSLATE=false
```

**Expected cost: $1-2/month** ✅

---

### **For Production (When Ready):**
```bash
# Use the .env.production file
cp .env.production .env

# Deploy with FULL mode
TRANSLATION_MODE=full
ENABLE_AMAZON_TRANSLATE=true
```

**Expected cost: $40-60/month** (with real users)

---

## 🔒 Safety Limits (Always Active)

Even in FULL mode, you have these safety nets:

### **1. Daily Translation Limit**
```bash
MAX_TRANSLATIONS_PER_DAY=1000
```
- Prevents runaway costs
- Service returns error after limit
- Resets every day at midnight UTC

### **2. Daily Cost Limit**
```bash
MAX_DAILY_COST_USD=5.00
```
- Automatically stops translations when limit reached
- Returns cached translations only
- Email alert sent to you

### **3. User Whitelist**
```bash
ALLOWED_TEST_USERS=user1@email.com,user2@email.com
```
- Only these users can use translation
- Everyone else gets English only
- Perfect for beta testing

### **4. Language Restrictions**
```bash
ALLOWED_LANGUAGES=en,hi,mr
```
- Only translate to these languages
- Reduces cost by 50% (3 languages vs 6)

### **5. Rate Limiting**
```bash
RATE_LIMIT_PER_MINUTE=10
```
- Prevents abuse
- Max 10 requests per minute per IP during testing
- Increase to 60 for production

---

## 📊 Cost Comparison by Mode

| Mode | Amazon Translate | DynamoDB | Lambda | CloudWatch | **TOTAL/month** |
|------|------------------|----------|--------|------------|-----------------|
| **DISABLED** | $0 | $0.50 | $1.00 | $0 | **$1.50** ✅ |
| **MOCK** | $0 | $0.50 | $1.00 | $0 | **$1.50** ✅ |
| **CACHE_ONLY** | $0 | $1.50 | $1.00 | $0 | **$2.50** ✅ |
| **FULL (Limited)** | $5.00 | $1.50 | $1.00 | $0 | **$7.50** ⚠️ |
| **FULL (Production)** | $29.10 | $1.82 | $3.08 | $6.49 | **$40.64** 💰 |

---

## 🎛️ How to Switch Modes

### **Option 1: Update Lambda Environment Variables (Recommended)**
```bash
# Switch to MOCK mode (FREE)
aws lambda update-function-configuration \
  --function-name vyaparai-translation-service \
  --environment "Variables={
    TRANSLATION_MODE=mock,
    ENABLE_AMAZON_TRANSLATE=false,
    MAX_TRANSLATIONS_PER_DAY=100,
    MAX_DAILY_COST_USD=1.00,
    ...
  }"

# Takes effect immediately (no redeployment needed!)
```

### **Option 2: Use Pre-configured .env files**
```bash
# For testing
cp .env.testing .env
# Then redeploy

# For development
cp .env.development .env
# Then redeploy

# For production
cp .env.production .env
# Then redeploy
```

---

## 🧪 Testing Each Mode

### **Test MOCK Mode:**
```bash
# Set mode
aws lambda update-function-configuration \
  --function-name vyaparai-translation-service \
  --environment Variables={TRANSLATION_MODE=mock}

# Test
curl https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com/api/v1/products/PROD-001 \
  -H "Accept-Language: hi" \
  -H "X-API-Key: test-key-12345"

# Response will have [MOCK] suffix
{
  "productName": "टाटा नमक [MOCK]",
  "fromCache": false
}
```

### **Test CACHE_ONLY Mode:**
```bash
# Set mode
aws lambda update-function-configuration \
  --function-name vyaparai-translation-service \
  --environment Variables={TRANSLATION_MODE=cache_only}

# Test with uncached product (returns English)
curl https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com/api/v1/products/PROD-001 \
  -H "Accept-Language: hi"

# Response will be in English (no translation)
{
  "productName": "Tata Salt",
  "fromCache": false
}
```

### **Test FULL Mode:**
```bash
# Set mode
aws lambda update-function-configuration \
  --function-name vyaparai-translation-service \
  --environment Variables={TRANSLATION_MODE=full,ENABLE_AMAZON_TRANSLATE=true}

# Test (will call Amazon Translate API - costs money!)
curl https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com/api/v1/products/PROD-001 \
  -H "Accept-Language: hi"

# Response will have real translation
{
  "productName": "टाटा नमक",
  "fromCache": false
}
```

---

## 📈 Check Current Usage & Cost

### **API Endpoint: /api/v1/cost-info**
```bash
curl https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com/api/v1/cost-info \
  -H "X-API-Key: your-key"

# Response
{
  "translation_mode": "mock",
  "amazon_translate_enabled": false,
  "cache_enabled": true,
  "metrics_enabled": false,
  "max_translations_per_day": 100,
  "max_daily_cost_usd": 1.00,
  "allowed_languages": ["en", "hi"],
  "estimated_daily_cost": 0.02,
  "current_usage": {
    "date": "2025-10-18",
    "translation_count": 15,
    "estimated_cost_usd": 0.00,
    "remaining_translations": 85,
    "remaining_budget_usd": 1.00,
    "usage_percentage": 15.0
  }
}
```

---

## ⚠️ What Happens When Limits Are Reached?

### **Daily Translation Limit Exceeded:**
```json
{
  "error": "Daily translation limit exceeded: 100",
  "message": "Limit resets at midnight UTC",
  "fallback": "Returning cached translations only"
}
```

### **Daily Cost Limit Exceeded:**
```json
{
  "error": "Daily cost limit exceeded: $1.00",
  "message": "Service switched to CACHE_ONLY mode",
  "current_cost": "$1.05"
}
```

### **User Not Whitelisted:**
```json
{
  "error": "Translation service restricted",
  "message": "Contact admin to enable translation",
  "fallback": "English content returned"
}
```

---

## 🎯 Recommended Settings for Your Testing

Since you said **"few users testing the system"**, here's your ideal config:

```bash
# .env file
TRANSLATION_MODE=mock                    # FREE translations
ENABLE_AMAZON_TRANSLATE=false           # No API calls
ENABLE_CACHE=true                       # Use cache if available
ENABLE_CLOUDWATCH_METRICS=false         # Save $3/month
ENABLE_DETAILED_LOGGING=false           # Save $3/month
MAX_TRANSLATIONS_PER_DAY=100            # Enough for testing
MAX_DAILY_COST_USD=0.50                 # Safety limit
ALLOWED_TEST_USERS=your@email.com       # Only you
ALLOWED_LANGUAGES=en,hi                 # Only 2 languages
RATE_LIMIT_PER_MINUTE=10                # Low limit for testing
```

**Expected cost: $1.50/month** (just Lambda + DynamoDB, no translation)

---

## 🚀 When to Upgrade Modes

| Sign | Action |
|------|--------|
| Testing UI/frontend | Use **MOCK** mode |
| Need real translations for 5-10 products | Pre-translate once, use **CACHE_ONLY** |
| Beta with 10-50 users | Use **FULL** with strict limits ($5/day) |
| Launch with 100+ users | Use **FULL** production mode ($40-60/month) |

---

## ✅ Summary

**For your current situation (testing with few users):**

1. **Use MOCK mode** - Cost: **$1.50/month** ✅
2. Set `MAX_DAILY_COST_USD=1.00` for safety
3. Whitelist only test users
4. Enable only 2 languages (en, hi)
5. Monitor with `/api/v1/cost-info` endpoint

**When you get real users:**

1. Switch to **FULL mode**
2. Increase limits gradually
3. Monitor costs daily
4. Scale based on actual usage

---

## 📞 Need Help?

- Check costs: `/api/v1/cost-info`
- Switch modes: Update Lambda env vars (takes 30 seconds)
- Emergency stop: Set `TRANSLATION_MODE=disabled`

**You have full control! No surprises.** 🎉
