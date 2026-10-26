#!/usr/bin/env bash
# Section 5 (curl) — the same auth/validation checks, with real curl against a
# live uvicorn server started by serve_mocked.py. Prints one PASS/FAIL line per
# check and a summary. Usage: bash tests/stress_suite/live_curl_checks.sh [base_url]
set -u
BASE="${1:-http://127.0.0.1:8765}"
pass=0; fail=0
check() { # name expected actual
  if [[ "$2" == *"|$3|"* ]]; then echo "PASS  $1 (HTTP $3)"; pass=$((pass+1)); else echo "FAIL  $1 expected $2 got $3"; fail=$((fail+1)); fi
}
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
json() { curl -s -H 'Content-Type: application/json' "$@"; }

A_TOK=$(json -X POST "$BASE/auth/register" -d '{"email":"alice@example.com","password":"alice-password"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
B_TOK=$(json -X POST "$BASE/auth/register" -d '{"email":"bob@example.com","password":"bob-password1"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
PID=$(json -X POST "$BASE/portfolios" -H "Authorization: Bearer $A_TOK" -d '{"name":"alice","benchmark":"SPY"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
json -X POST "$BASE/portfolios/$PID/holdings" -H "Authorization: Bearer $A_TOK" -d '[{"ticker":"T000","shares":10},{"ticker":"T001","shares":5}]' >/dev/null

check "owner GET portfolio"            "|200|" "$(code "$BASE/portfolios/$PID" -H "Authorization: Bearer $A_TOK")"
check "owner GET stress"               "|200|" "$(code "$BASE/portfolios/$PID/stress" -H "Authorization: Bearer $A_TOK")"
for ep in "" /risk /factors /correlation /optimize /stress; do
  check "no token GET $ep"             "|401|" "$(code "$BASE/portfolios/$PID$ep")"
  check "bob GET alice $ep"            "|400|404|" "$(code "$BASE/portfolios/$PID$ep" -H "Authorization: Bearer $B_TOK")"
done
check "bob POST holdings into alice"   "|404|" "$(code -X POST "$BASE/portfolios/$PID/holdings" -H "Authorization: Bearer $B_TOK" -H 'Content-Type: application/json' -d '[{"ticker":"T002","shares":1}]')"
check "bob CSV into alice"             "|404|" "$(code -X POST "$BASE/portfolios/$PID/holdings/csv" -H "Authorization: Bearer $B_TOK" -F 'file=@-;filename=p.csv' <<< $'ticker,shares\nT002,1')"
check "bob DELETE alice"               "|401|404|405|" "$(code -X DELETE "$BASE/portfolios/$PID" -H "Authorization: Bearer $B_TOK")"
check "garbage token"                  "|401|" "$(code "$BASE/portfolios/$PID" -H 'Authorization: Bearer abc.def.ghi')"
check "alg=none token"                 "|401|" "$(code "$BASE/portfolios/$PID" -H 'Authorization: Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJ4In0.')"
check "token in query string ignored"  "|401|" "$(code "$BASE/portfolios/$PID?token=$A_TOK")"
check "malformed JSON body"            "|422|" "$(code -X POST "$BASE/portfolios/$PID/holdings" -H "Authorization: Bearer $A_TOK" -H 'Content-Type: application/json' -d '[{"ticker":')"
check "text/plain body"                "|422|" "$(code -X POST "$BASE/portfolios/$PID/holdings" -H "Authorization: Bearer $A_TOK" -H 'Content-Type: text/plain' -d 'hello')"
check "negative shares"                "|422|" "$(code -X POST "$BASE/portfolios/$PID/holdings" -H "Authorization: Bearer $A_TOK" -H 'Content-Type: application/json' -d '[{"ticker":"T002","shares":-1}]')"
check "NaN shares (JSON literal)"      "|400|422|" "$(code -X POST "$BASE/portfolios/$PID/holdings" -H "Authorization: Bearer $A_TOK" -H 'Content-Type: application/json' -d '[{"ticker":"T002","shares":NaN}]')"
check "Infinity shares (JSON literal)" "|400|422|" "$(code -X POST "$BASE/portfolios/$PID/holdings" -H "Authorization: Bearer $A_TOK" -H 'Content-Type: application/json' -d '[{"ticker":"T002","shares":Infinity}]')"
check "injection-shaped ticker"        "|422|" "$(code -X POST "$BASE/portfolios/$PID/holdings" -H "Authorization: Bearer $A_TOK" -H 'Content-Type: application/json' -d "[{\"ticker\":\"T0'; DROP TABLE holdings;--\",\"shares\":1}]")"
check "8 MB CSV rejected"              "|413|" "$(head -c 8000000 /dev/zero | tr '\0' 'a' | curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/portfolios/$PID/holdings/csv" -H "Authorization: Bearer $A_TOK" -F 'file=@-;filename=big.csv')"

# Brute-force: 12 wrong logins from one client -> must see 429 by the 11th.
codes=""; for i in $(seq 1 12); do codes="$codes $(code -X POST "$BASE/auth/login" -H 'Content-Type: application/json' -d '{"email":"alice@example.com","password":"wrong-password"}')"; done
last=$(echo $codes | awk '{print $NF}')
check "login brute force throttled (codes:$codes)" "|429|" "$last"
# Informational: uvicorn trusts X-Forwarded-For from 127.0.0.1 by default, so the
# limiter key (client IP) can be changed by the caller when the peer is trusted.
check "throttled login still 429 with spoofed X-Forwarded-For" "|429|" "$(code -X POST "$BASE/auth/login" -H 'Content-Type: application/json' -H 'X-Forwarded-For: 9.9.9.9' -d '{"email":"alice@example.com","password":"wrong-password"}')"

# Default 60/min limit on analytics: 65 requests to /stress.
codes429=0; for i in $(seq 1 65); do c=$(code "$BASE/portfolios/$PID/stress" -H "Authorization: Bearer $A_TOK"); [ "$c" = 429 ] && codes429=$((codes429+1)); done
check "65x /stress hits default 60/min limit ($codes429 x 429)" "|yes|" "$([ $codes429 -ge 5 ] && echo yes || echo no)"

echo "SUMMARY: $pass passed, $fail failed"
