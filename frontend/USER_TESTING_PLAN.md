# User Testing Plan: db8r-eval-utility Frontend

## Prerequisites

- Python 3.12+ with Poetry installed
- Node.js 20+ with npm
- Terminal access

---

## Part 1: Setup

### 1.1 Install Backend Dependencies

```bash
cd /home/jrisch/projects/db8r-system/db8r-eval-utility
poetry install
```

### 1.2 Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 1.3 Initialize the Database

The database initializes automatically on first startup, but you can verify:

```bash
cd /home/jrisch/projects/db8r-system/db8r-eval-utility
mkdir -p gold fixtures
```

### 1.4 Configure Admin User

Create a `.env` file in the project root to bootstrap an admin user:

```bash
cat > .env << 'EOF'
EVAL_ADMIN_EMAIL=admin@example.com
EVAL_ADMIN_INITIAL_PASSWORD=adminpass123
EVAL_SESSION_COOKIE_SECURE=false
EOF
```

**Environment Variables:**

| Variable | Description | Default |
|----------|-------------|---------|
| `EVAL_ADMIN_EMAIL` | Bootstrap admin email | None |
| `EVAL_ADMIN_INITIAL_PASSWORD` | Bootstrap admin password (min 8 chars) | None |
| `EVAL_DATABASE_URL` | Database connection | `sqlite:///gold/gold.db` |
| `EVAL_FIXTURES_DIR` | Fixtures directory | `./fixtures` |
| `EVAL_SESSION_COOKIE_SECURE` | HTTPS-only cookies | `false` |

---

## Part 2: Running the Application

### 2.1 Start the Backend (Terminal 1)

```bash
cd /home/jrisch/projects/db8r-system/db8r-eval-utility
poetry run uvicorn eval_utility.server:app --reload --port 8002
```

You should see:
```
Bootstrapped admin user: admin@example.com
INFO:     Uvicorn running on http://127.0.0.1:8002
```

### 2.2 Start the Frontend (Terminal 2)

```bash
cd /home/jrisch/projects/db8r-system/db8r-eval-utility/frontend
npm run dev
```

You should see:
```
VITE v6.x.x ready in XXX ms
➜  Local:   http://localhost:5173/
```

### 2.3 Access the Application

Open **http://localhost:5173** in your browser.

---

## Part 3: User Configuration

### 3.1 Admin Login

1. Navigate to http://localhost:5173/login
2. Enter credentials from `.env`:
   - Email: `admin@example.com`
   - Password: `adminpass123`
3. Click "Sign in"

**Expected:** Redirected to Dashboard. Sidebar shows "Admin" section with Users and Capture links.

### 3.2 Create an Annotator Account

1. Click "Users" in the Admin section of the sidebar
2. Click "Invite User"
3. Enter:
   - Email: `annotator@example.com`
   - Role: Annotator
4. Click "Create Invite"
5. **Copy the invite URL** shown in the dialog

### 3.3 Accept Invite (New Browser/Incognito)

1. Open the invite URL in a new incognito window
2. Set a password (min 8 characters)
3. Click "Create Account"
4. Click "Go to Login"
5. Login with the new credentials

**Expected:** Dashboard without Admin section (annotators don't see admin links).

---

## Part 4: Feature Testing Checklist

### 4.1 Authentication

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Login success | Enter valid credentials, click Sign in | Redirect to Dashboard |
| Login failure | Enter wrong password | "Invalid email or password" error |
| Logout | Click "Sign out" in header | Redirect to login page |
| Session persistence | Refresh page after login | Stay logged in |
| Protected routes | Visit /admin/users as annotator | Redirect to Dashboard |

### 4.2 Dashboard

| Test | Steps | Expected Result |
|------|-------|-----------------|
| View dashboard | Login and visit / | See task queue cards, dataset stats |
| T1 link | Click "Start judging" | Navigate to /queue/t1 |
| T2 link | Click "Start annotating" | Navigate to /queue/t2 |
| Report link | Click "View report" | Navigate to /report |

### 4.3 Admin: User Management

| Test | Steps | Expected Result |
|------|-------|-----------------|
| View users | Go to /admin/users | See table with admin user |
| Invite user | Click Invite, fill form | Invite URL displayed |
| Disable user | Click "Disable" on a user | Status changes to "Disabled" |
| Enable user | Click "Enable" on disabled user | Status changes to "Active" |

### 4.4 Admin: Capture Jobs

| Test | Steps | Expected Result |
|------|-------|-----------------|
| View capture form | Go to /admin/capture | See mode selection, input fields |
| Mode A (Search) | Select Search, enter query, click Run | Error (ClaimCheck not running) or success |
| Mode B (Extract) | Select Extract, enter query | Form updates |
| Foraging | Select Foraging | Shows claim text area instead of query input |

**Note:** Capture will fail unless ClaimCheck/db8r-mcts are running. This tests the UI flow.

### 4.5 T1: Retrieval Judgment

**Prerequisite:** Need claims and documents in the database. See "Seeding Test Data" below.

| Test | Steps | Expected Result |
|------|-------|-----------------|
| View claim | Go to /t1/{claimId} | See claim text with badges |
| Rate document | Click a relevance button (0-3) | Button highlights as selected |
| Save progress | Click "Save Progress" | Changes persist after refresh |
| Complete | Click "Complete & Next" | Redirects to dashboard |

### 4.6 T2: Span Annotation

**Prerequisite:** Need fixtures with documents in the database.

| Test | Steps | Expected Result |
|------|-------|-----------------|
| View document | Go to /t2/{documentId} | See document text in annotator |
| Create span | Click-drag to select text | New span created (gray/unreviewed) |
| Word snap | Select partial word | Snap expands to full word |
| Char-precise | Hold Alt, drag | Exact character selection |
| Click span | Click an existing span | Popover appears with actions |
| Toggle claim-bearing | Click "Mark Claim-bearing" | Span turns green |
| Toggle not claim-bearing | Click "Mark Not Claim-bearing" | Span turns red |
| Delete span | Click "Delete" in popover | Span removed |
| Resize span | Drag span edge handles | Span boundary updates |
| Overlapping spans | Click where spans overlap | Menu appears to select which span |
| Document flags | Toggle "Exhaustively annotated" | Checkbox updates |
| Save flags | Click "Save Flags" | Persists after refresh |
| Unsaved warning | Make changes, try to navigate away | Browser confirmation dialog |

### 4.7 T3: Stance (Deferred)

| Test | Steps | Expected Result |
|------|-------|-----------------|
| View T3 | Go to /t3/{claimId} | See "Coming in v2" message |

### 4.8 Report View

| Test | Steps | Expected Result |
|------|-------|-----------------|
| View report (empty) | Go to /report with no data | "No scorer report available" message |
| View report (with data) | Run scorer, then view | Metrics displayed in cards/tables |

---

## Part 5: Seeding Test Data

To test T1/T2 views, you need claims and fixtures. Run the corpus seeder:

```bash
cd /home/jrisch/projects/db8r-system/db8r-eval-utility
poetry run python -c "
from eval_utility.corpus import seed_corpus
from eval_utility.store import GoldStore
from eval_utility.database import init_db

init_db()
store = GoldStore()
seed_corpus(store)
print('Seeded 72 claims')
"
```

### Create a Test Fixture

For T2 testing, create a simple fixture manually:

```bash
mkdir -p fixtures
cat > fixtures/test-fixture-001.json << 'EOF'
{
  "fixture_id": "test-fixture-001",
  "capture_mode": "extract",
  "schema_version": "gold_v1",
  "captured_at": "2024-01-01T00:00:00Z",
  "documents": [
    {
      "document_id": "doc-001",
      "source_url": "https://example.com/article",
      "source_title": "Test Article for Annotation",
      "source_text_hash": "abc123hash",
      "source_text": "This is a sample document with several claims. The economy grew by 5% last year. Climate change is accelerating. New studies show promising results. This document contains evidence that can be annotated for the evaluation pipeline.",
      "provider": "test"
    }
  ],
  "spans": [],
  "retrieval_results": []
}
EOF
```

Then navigate to: **http://localhost:5173/t2/abc123hash**

---

## Part 6: Performance Testing

### SpanAnnotator with Large Documents

Test with 50k+ character documents to verify virtualization:

```python
# Generate large test fixture
import json

large_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 1000
doc = {
    "fixture_id": "large-doc-001",
    "capture_mode": "extract",
    "schema_version": "gold_v1",
    "captured_at": "2024-01-01T00:00:00Z",
    "documents": [{
        "document_id": "large-doc",
        "source_url": "https://example.com/large",
        "source_title": "Large Document Test",
        "source_text_hash": "largehash001",
        "source_text": large_text,
        "provider": "test"
    }],
    "spans": [],
    "retrieval_results": []
}

with open("fixtures/large-doc-001.json", "w") as f:
    json.dump(doc, f)
```

Navigate to **http://localhost:5173/t2/largehash001** and verify:
- Scrolling is smooth
- Creating spans doesn't lag
- Page doesn't freeze

---

## Part 7: Error Handling

| Test | Steps | Expected Result |
|------|-------|-----------------|
| 401 handling | Expire session (clear cookies), try action | Redirect to login |
| 404 document | Visit /t2/nonexistent | "Document not found" error |
| 404 claim | Visit /t1/nonexistent | "Claim not found" error |
| Network error | Stop backend, try action | Error state shown |

---

## Part 8: Browser Compatibility

Test in:
- Chrome (primary)
- Firefox
- Safari (if available)

Key things to verify:
- Text selection in SpanAnnotator works
- CSS renders correctly
- Session cookies work

---

## Quick Reference

| URL | Purpose |
|-----|---------|
| http://localhost:5173/login | Login page |
| http://localhost:5173/ | Dashboard |
| http://localhost:5173/t1/{claimId} | T1 Retrieval view |
| http://localhost:5173/t2/{documentId} | T2 Span annotation |
| http://localhost:5173/report | Scorer report |
| http://localhost:5173/admin/users | User management |
| http://localhost:5173/admin/capture | Capture jobs |
| http://localhost:8002/docs | Backend API docs (Swagger) |
| http://localhost:8002/openapi.json | OpenAPI spec |

---

## Troubleshooting

### "Failed to fetch" errors
- Check backend is running on port 8002
- Check browser console for CORS errors
- Verify `.env` has `EVAL_CORS_ORIGIN=*` or correct origin

### Login doesn't work
- Verify admin credentials in `.env`
- Check backend logs for "Bootstrapped admin user" message
- Clear browser cookies and try again

### Spans don't render
- Check browser console for JavaScript errors
- Verify document has `source_text` in fixture
- Check that `documentId` matches `source_text_hash`

### Session expires immediately
- Check `EVAL_SESSION_COOKIE_SECURE=false` for local dev
- Ensure not using HTTPS locally with secure cookie flag
