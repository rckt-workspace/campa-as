# Meta Graph API Diagnosis Guide

The smoke tests revealed that the expanded query configuration may not be working correctly.

This guide provides step-by-step diagnosis scripts to identify the issue.

## Prerequisites

Ensure these environment variables are set:

```bash
export META_ACCESS_TOKEN="your_token"
export META_IG_USER_ID="your_ig_user_id"
export META_GRAPH_API_VERSION="v26.0"
```

## Step 1: Test Minimal Query

Run the **minimal** query that was verified to work in Graph API Explorer:

```bash
python backend/scripts/test_minimal_query.py
```

**Expected result:** Should retrieve posts from @newbodycol

This tells us if Business Discovery works at all, or if there's a configuration/permission issue.

### If Minimal Query FAILS:
- The issue is **not** the expanded fields
- The issue is one of:
  - Invalid credentials
  - Token doesn't have required permissions
  - Source IG User ID is incorrect
  - Business Discovery not enabled for the app

**Action:** Fix credentials and try again. Do NOT proceed to progressive field testing.

### If Minimal Query SUCCEEDS:
- Business Discovery works
- Proceed to **Step 2**

## Step 2: Progressive Field Testing

Once the minimal query works, test which fields are supported:

```bash
python backend/scripts/diagnose_meta_fields.py
```

**This script will:**
1. Test MINIMAL (baseline)
2. Add `media_url`
3. Add `thumbnail_url`
4. Add `media_product_type`
5. Add `children{id,media_type,media_url}`
6. Add `children{id,media_type,media_url,thumbnail_url}`

After each test, you'll see:
- HTTP status code
- Number of posts retrieved
- Whether it worked or failed

**Output table:**
```
Field Set                                | HTTP | Posts
MINIMAL (baseline - known working)       |  ✅  | X posts
A: Add media_url                         |  ❌ or ✅ | X posts
...etc
```

### Result Interpretation:

- **If all fields work:** Update MetaInstagramProvider to request all expanded fields
- **If some fields fail:** Update to use the working subset
- **If only MINIMAL works:** Stick with minimal fields; add visual fields via alternative method

## Step 3: Production Smoke Test

Once you identify the working field set:

1. Update `MetaInstagramProvider._fetch_business_discovery_page()` with the working fields
2. Run the corrected smoke test:

```bash
python backend/scripts/smoke_test_meta_real.py
```

**CRITICAL VALIDATIONS:**
- Count mode MUST return >12 posts
- Date mode MUST return posts with valid dates
- Four accounts MUST be accessible (or correctly report why not)

## Step 4: Fix MetaInstagramProvider

Based on the diagnosis results:

1. Open `backend/app/providers/meta_instagram.py`
2. Find the `_fetch_business_discovery_page()` method
3. Update the `media_fields` to match the working field set from Step 2
4. Update `_media_to_post()` to handle available fields (remove handling for unsupported fields)
5. Run tests: `pytest -q tests/test_meta_instagram_provider.py`
6. Re-run smoke test

## Troubleshooting

### "target_not_found" with >0 posts
This is actually a successful response. The provider is correctly handling Business Discovery.

### No posts from valid account
Check:
1. Account is Professional (Business or Creator)
2. Account is public or you have permission
3. Account is not restricted in any way

### HTTP 400 with field-specific error
The field mentioned is not supported in Business Discovery.
Remove that field and try again.

### HTTP 401/403
Token issue:
1. Verify token hasn't expired
2. Verify token has Instagram scopes
3. Regenerate token if needed
