# VyaparAI - Post Company Registration TODO

**Document Version:** 1.0
**Last Updated:** January 18, 2026
**Status:** Pending Company Registration

---

## Overview

This document tracks all pending tasks that require company registration to complete. These items are blocked until the company is officially registered with the necessary government authorities.

---

## 1. SMS Service - Gupshup Integration

### Status: CODE COMPLETE, PENDING CREDENTIALS

The SMS service for OTP delivery has been fully implemented and deployed. It requires Gupshup Enterprise SMS credentials which need company registration for DLT compliance.

### Current State
| Component | Status |
|-----------|--------|
| SMS Service Code (`app/services/sms_service.py`) | ✅ Deployed |
| Auth Integration (Store Owner) | ✅ Deployed |
| Auth Integration (Customer) | ✅ Deployed |
| Gupshup Account | ❌ Pending |
| DLT Registration | ❌ Pending |

### Why Company Registration is Required
As per TRAI (Telecom Regulatory Authority of India) regulations, all businesses sending SMS in India must:
1. Register on a DLT (Distributed Ledger Technology) platform
2. This requires a registered business entity (company/LLP/proprietorship)
3. PAN, GST, and business documents are mandatory

### Action Items

#### Step 1: Gupshup Enterprise Account Setup
- [ ] Go to https://enterprise.smsgupshup.com/
- [ ] Sign up with company email
- [ ] Complete KYC with company documents:
  - Company PAN Card
  - GST Certificate
  - Certificate of Incorporation
  - Authorized Signatory ID Proof
- [ ] Note down credentials:
  - User ID: `_______________`
  - Password: `_______________`

#### Step 2: DLT Registration (Choose ONE platform)
| Platform | Portal URL |
|----------|-----------|
| Jio | https://trueconnect.jio.com/ |
| Airtel | https://www.airtel.in/business/commercial-communication |
| Vodafone-Idea | https://www.vilpower.in/ |
| BSNL | https://www.ucc-bsnl.co.in/ |

**DLT Registration Checklist:**
- [ ] Register as Principal Entity (PE)
- [ ] Submit company documents
- [ ] Get Principal Entity ID: `_______________`
- [ ] Register Sender ID (Header): `VYAPAR` or `_______________`
- [ ] Wait for Sender ID approval (2-7 days)

#### Step 3: Template Registration
Register the following OTP template on DLT portal:

**Template Content:**
```
Your VyaparAI verification code is {#var#}. Valid for 5 minutes. Do not share this code.
```

**Template Details:**
- [ ] Template Type: Transactional (Service Implicit)
- [ ] Template ID after approval: `_______________`

#### Step 4: Configure Lambda Environment Variables
Once all credentials are obtained, run:

```bash
aws lambda update-function-configuration \
  --function-name vyaparai-api-prod \
  --region ap-south-1 \
  --environment "Variables={
    GUPSHUP_USERID=<your_userid>,
    GUPSHUP_PASSWORD=<your_password>,
    GUPSHUP_SENDER_ID=VYAPAR,
    GUPSHUP_ENTITY_ID=<your_dlt_entity_id>,
    GUPSHUP_OTP_TEMPLATE_ID=<your_template_id>,
    <...keep existing variables...>
  }"
```

#### Step 5: Testing
- [ ] Send test OTP to registered phone number
- [ ] Verify SMS delivery
- [ ] Check delivery reports in Gupshup dashboard

### Estimated Costs
| Volume/Month | Cost (Approx) |
|--------------|---------------|
| 1,000 SMS | ₹150 - ₹250 |
| 5,000 SMS | ₹750 - ₹1,250 |
| 10,000 SMS | ₹1,500 - ₹2,500 |
| 25,000 SMS | ₹3,750 - ₹6,250 |
| 50,000 SMS | ₹7,500 - ₹12,500 |

### Timeline Estimate
| Task | Duration |
|------|----------|
| Gupshup Account Setup | 1-2 days |
| DLT Registration | 3-5 days |
| Sender ID Approval | 2-7 days |
| Template Approval | 1-3 days |
| **Total** | **7-17 days** |

---

## 2. Payment Gateway Integration

### Status: NOT STARTED

Payment gateway integration requires company registration and bank account.

### Recommended Providers for India
| Provider | Transaction Fee | Settlement |
|----------|----------------|------------|
| Razorpay | 2% + GST | T+2 days |
| PayU | 2% + GST | T+2 days |
| Cashfree | 1.9% + GST | T+1 day |
| PhonePe PG | 1.9% + GST | T+2 days |

### Requirements
- [ ] Company registration certificate
- [ ] Company PAN Card
- [ ] GST registration
- [ ] Current account in company name
- [ ] Cancelled cheque
- [ ] Business address proof
- [ ] Director/Signatory KYC

### Action Items
- [ ] Open company current account
- [ ] Apply for payment gateway
- [ ] Complete merchant onboarding
- [ ] Integrate payment API
- [ ] Test transactions in sandbox
- [ ] Go live with payments

---

## 3. GST Registration & Invoicing

### Status: PENDING

Required for B2B transactions and tax compliance.

### Action Items
- [ ] Apply for GST registration
- [ ] GST Number: `_______________`
- [ ] Configure GST in billing system
- [ ] Set up automated GST invoicing
- [ ] Integrate with accounting software (Tally/Zoho)

---

## 4. AWS Account - Production Setup

### Status: PARTIALLY COMPLETE

Current AWS account may be personal. Need to transition to company account.

### Action Items
- [ ] Create AWS account under company name
- [ ] Set up AWS Organizations
- [ ] Enable consolidated billing
- [ ] Apply for AWS Activate (startup credits)
- [ ] Migrate resources to company account
- [ ] Set up IAM roles and policies
- [ ] Enable CloudTrail for compliance

---

## 5. Domain & SSL

### Status: CHECK REQUIRED

Ensure domain is registered under company name.

### Action Items
- [ ] Verify domain ownership
- [ ] Transfer domain to company account if needed
- [ ] Set up company email (admin@vyaparai.com)
- [ ] Verify SSL certificates

---

## 6. Legal & Compliance

### Status: PENDING

### Action Items
- [ ] Draft Terms of Service
- [ ] Draft Privacy Policy (DPDP Act 2023 compliant)
- [ ] Draft Refund/Cancellation Policy
- [ ] Draft Seller Agreement (for marketplace)
- [ ] Trademark registration for "VyaparAI"
- [ ] Get legal review of all policies

---

## 7. Business Insurance

### Status: NOT STARTED

### Recommended Coverage
- [ ] Cyber liability insurance
- [ ] Professional indemnity insurance
- [ ] Directors & Officers (D&O) insurance

---

## 8. Third-Party Service Accounts

### Services Requiring Company Details
| Service | Purpose | Status |
|---------|---------|--------|
| Gupshup | SMS OTP | ❌ Pending |
| Firebase | Push Notifications | ✅ Active |
| Google Cloud | Maps/Translation | ⚠️ Review needed |
| AWS | Infrastructure | ⚠️ Review needed |
| Razorpay/PayU | Payments | ❌ Pending |
| Freshdesk/Zendesk | Customer Support | ❌ Pending |

---

## Priority Order

1. **HIGH PRIORITY** (Week 1-2 after registration)
   - [ ] Gupshup SMS setup (blocking OTP functionality)
   - [ ] Payment gateway setup (blocking monetization)
   - [ ] GST registration

2. **MEDIUM PRIORITY** (Week 2-4)
   - [ ] AWS account migration
   - [ ] Legal documents
   - [ ] Domain/email setup

3. **LOWER PRIORITY** (Month 2+)
   - [ ] Insurance
   - [ ] Trademark registration
   - [ ] Additional compliance

---

## Notes

- Keep all credentials in a secure password manager (1Password/Bitwarden)
- Document all account details in company records
- Set up 2FA on all critical accounts
- Create shared access for key team members

---

## Document History

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-18 | 1.0 | Initial document with Gupshup SMS requirements |

---

*This document should be updated as tasks are completed.*
