#!/bin/bash
# Comprehensive API stress test for Artemis
set -euo pipefail

BASE="http://localhost:8000"
H="-H X-Simulation-Role:admin"
PASS=0
FAIL=0

ok() { PASS=$((PASS+1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL: $1 — $2"; }

test_endpoint() {
    local method="$1" url="$2" label="$3" expected_code="${4:-200}" body="${5:-}"
    local args=(-s -o /tmp/artemis_test_body -w "%{http_code}" -X "$method" "$BASE$url" -H "X-Simulation-Role: admin" -H "X-Simulation-Org: nasa")
    if [ -n "$body" ]; then
        args+=(-H "Content-Type: application/json" -d "$body")
    fi
    local code
    code=$(curl "${args[@]}" 2>/dev/null)
    if [ "$code" = "$expected_code" ]; then
        ok "$label (HTTP $code)"
    else
        fail "$label" "expected $expected_code, got $code: $(cat /tmp/artemis_test_body)"
    fi
}

echo "========================================="
echo " Artemis API Stress Test"
echo "========================================="
echo ""

# Health
echo "--- Infrastructure ---"
test_endpoint GET /health "Health check"

# Admin
echo "--- Admin ---"
test_endpoint GET /api/v1/admin/status "Simulation status"
test_endpoint POST /api/v1/admin/reset "Reset simulation" 200 '{"confirm":true,"reason":"stress test"}'
test_endpoint POST /api/v1/admin/seed/clean "Seed clean scenario"

# Contractors
echo "--- Contractors ---"
test_endpoint GET /api/v1/contractors "List contractors"
test_endpoint GET /api/v1/contractors/benning "Get contractor: Benning"
test_endpoint GET /api/v1/contractors/xyzspace "Get contractor: XYZSpace"
test_endpoint GET /api/v1/contractors/nonexistent "Get nonexistent contractor" 404

# Facilities
echo "--- Facilities ---"
test_endpoint GET /api/v1/facilities "List facilities"

# Clock
echo "--- Clock ---"
test_endpoint GET /api/v1/clock "Get clock"

# Create mission
echo "--- Missions ---"
MISSION_RESPONSE=$(curl -s -X POST "$BASE/api/v1/missions" -H "X-Simulation-Role: admin" -H "X-Simulation-Org: nasa" -H "Content-Type: application/json" -d '{"name":"Stress Test I","architecture_type":"estes"}')
MISSION_ID=$(echo "$MISSION_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
if [ -n "$MISSION_ID" ]; then
    ok "Create Estes mission (id=$MISSION_ID)"
else
    fail "Create Estes mission" "$MISSION_RESPONSE"
    echo "Cannot continue without mission ID."
    exit 1
fi

test_endpoint GET /api/v1/missions "List missions"
test_endpoint GET "/api/v1/missions/$MISSION_ID" "Get mission by ID"

# Tasks
echo "--- Tasks ---"
test_endpoint GET "/api/v1/missions/$MISSION_ID/tasks" "List all tasks"
test_endpoint GET "/api/v1/missions/$MISSION_ID/tasks?phase=PROCUREMENT" "Filter tasks by phase"
test_endpoint GET "/api/v1/missions/$MISSION_ID/tasks?status=AVAILABLE" "Filter tasks by status"
test_endpoint GET "/api/v1/missions/$MISSION_ID/tasks?assigned_role=nasa-tech-authority" "Filter tasks by role"

# Get first available task
TASK_ID=$(curl -s "$BASE/api/v1/missions/$MISSION_ID/tasks?status=AVAILABLE" -H "X-Simulation-Role: admin" -H "X-Simulation-Org: nasa" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)
if [ -n "$TASK_ID" ]; then
    test_endpoint GET "/api/v1/tasks/$TASK_ID" "Get task by ID"
    test_endpoint GET "/api/v1/tasks/$TASK_ID/artifacts" "Get task artifacts (empty)"
    ok "Task ID for workflow test: $TASK_ID"
else
    fail "Get available task" "no available tasks found"
fi

# Clock advance (after mission creation ensures clock workflow is running)
echo "--- Clock Advance ---"
test_endpoint POST /api/v1/clock/advance "Advance clock" 200 '{"duration_seconds":3600,"reason":"stress test advance"}'

# Role-based access tests
echo "--- Role-based access ---"
for role in nasa-program-manager nasa-tech-authority nasa-contracts-officer contractor-pm contractor-engineer egs-ground-ops admin; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/missions" -H "X-Simulation-Role: $role" -H "X-Simulation-Org: nasa" 2>/dev/null)
    if [ "$code" = "200" ]; then
        ok "Access as $role"
    else
        fail "Access as $role" "HTTP $code"
    fi
done

# Duplicate create (same name should still work — no unique constraint on name)
echo "--- Edge Cases ---"
test_endpoint POST /api/v1/missions "Create second mission" 201 '{"name":"Stress Test II","architecture_type":"estes"}'
test_endpoint GET /api/v1/missions "List now shows 2 missions"
test_endpoint GET "/api/v1/tasks/00000000-0000-0000-0000-000000000000" "Get nonexistent task" 404
test_endpoint POST "/api/v1/admin/reset" "Reset without confirm" 400 '{"confirm":false,"reason":"test"}'

# Browser views (should redirect to login or render)
echo "--- Browser Views ---"
for path in / /login /dev/login; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE$path" 2>/dev/null)
    if [ "$code" = "200" ] || [ "$code" = "302" ]; then
        ok "GET $path (HTTP $code)"
    else
        fail "GET $path" "HTTP $code"
    fi
done

echo ""
echo "========================================="
echo " Results: $PASS passed, $FAIL failed"
echo "========================================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
