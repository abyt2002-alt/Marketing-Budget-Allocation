# Test Plan: Intent Resolution Conditional Filtering

## How to Test

1. Start the backend server
2. Start the frontend development server
3. Navigate to the Scenario Generation section
4. Select a brand and multiple markets (at least 5-10 markets)
5. Enter test prompts and verify the resolved intent

---

## Test Cases

### Test 1: Losing Market Share Condition
**Prompt:** `Increase media allocation in markets where I am losing market share`

**Expected Result:**
- Only markets with `change_in_market_share_band` = "mild_negative" or "strong_negative" should have "increase" action
- Other markets should have intelligence-based actions (protect/hold/recover)
- Explanation note should say: "Conditional market filtering applied: X markets matched the specified criteria from your prompt."

**How to Verify:**
- Check the "Resolved Intent" section
- Look at "Action Summary" - should NOT show all markets under "Increase"
- Count markets under "Increase" - should be less than total selected markets

---

### Test 2: Gaining Market Share Condition
**Prompt:** `Protect markets where I am gaining market share`

**Expected Result:**
- Only markets with positive share change should have "protect" action
- Other markets should have their default actions

---

### Test 3: High CPR Condition
**Prompt:** `Reduce spend in markets with high CPR`

**Expected Result:**
- Only markets with `avg_cpr_band` = "high_cost" should have "decrease" action
- Other markets should have their default actions

---

### Test 4: Multiple Conditions (Complex)
**Prompt:** `Increase in markets where I am losing share, and protect markets where I am gaining share`

**Expected Result:**
- Markets losing share: "increase" action
- Markets gaining share: "protect" action
- Other markets: default intelligence-based actions

---

### Test 5: Explicit Market Names (Should Still Work)
**Prompt:** `Increase media allocation in Maharashtra and Kerala`

**Expected Result:**
- Maharashtra: "increase"
- Kerala: "increase"
- Other markets: default actions
- Explanation note: "Explicit market instructions from the prompt were given precedence over inferred rankings."

---

### Test 6: Global Action (No Conditions)
**Prompt:** `Grow volume across all markets`

**Expected Result:**
- ALL markets should have "increase" action (or intelligence-based if not "hold")
- This is the old behavior - should still work when no conditions are specified

---

### Test 7: Re-resolve Intent Button
**Steps:**
1. Enter a prompt and click "Resolve Intent"
2. Wait for resolution to complete
3. Verify "Re-resolve Intent" button appears
4. Click "Re-resolve Intent"
5. Verify intent is resolved again (may get different results if AI-based)

**Expected Result:**
- Button appears when status is "ready"
- Button is disabled during resolution
- Clicking re-resolves without losing the prompt
- New resolved intent replaces the old one

---

## Debugging Tips

### If ALL markets still get the same action:

1. Check backend logs for errors
2. Verify market intelligence data has `change_in_market_share_band` field
3. Check if any markets actually match the condition (e.g., have negative share change)
4. Add debug logging to `_filter_markets_by_condition()` to see what's being filtered

### If conditional filtering doesn't work:

1. Verify the prompt contains "where" or "with" keywords
2. Check if the condition patterns match (case-insensitive)
3. Verify `market_rows` parameter is being passed correctly
4. Check if market intelligence data is loaded properly

### If Re-resolve button doesn't appear:

1. Check if `scenarioIntentStatus === 'ready'`
2. Check if `scenarioIntentResolved` is not null
3. Verify the button is not hidden by CSS
4. Check browser console for React errors

---

## Success Criteria

✅ Conditional filtering correctly identifies markets matching the criteria
✅ Only matching markets get the specified action
✅ Non-matching markets retain intelligence-based actions
✅ Explanation notes clearly indicate conditional filtering was used
✅ Explicit market names still work as before
✅ Global actions still work when no conditions specified
✅ Re-resolve Intent button appears and functions correctly
✅ No TypeScript or Python errors in console/logs

---

## Known Limitations

1. Only supports single-level conditions (can't do "where X AND Y")
2. Condition keywords must include "where" or "with" to trigger filtering
3. Market intelligence data must be available for filtering to work
4. If no markets match the condition, the prompt may fall back to global action

---

## Date: 2026-04-21
