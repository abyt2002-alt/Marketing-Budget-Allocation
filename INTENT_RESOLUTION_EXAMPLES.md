# Intent Resolution: Before & After Examples

## Example 1: Losing Market Share

### Prompt
```
Increase media allocation in markets where I am losing market share
```

### BEFORE FIX ❌
```
Resolved Intent:
- Objective: Volume
- Global Action: Increase
- Primary Anchor: Category Salience

Action Summary:
  Increase: 15 markets
    - Maharashtra
    - UP-UK
    - Kerala
    - Tamil Nadu
    - Karnataka
    - Gujarat
    - West Bengal
    - Andhra Pradesh
    - Rajasthan
    - Madhya Pradesh
    - ... (all selected markets)

Notes:
- "No explicit market instructions found; global action preference applied."
```

**Problem:** ALL 15 markets got "increase" action, even though only 2-3 were actually losing market share.

---

### AFTER FIX ✅
```
Resolved Intent:
- Objective: Volume
- Global Action: Increase
- Primary Anchor: Change in Market Share

Action Summary:
  Increase: 3 markets
    - Kerala (share change: -2.3%)
    - Gujarat (-1.8%)
    - Rajasthan (-0.9%)
  
  Protect: 5 markets
    - Maharashtra (high share, positive momentum)
    - Tamil Nadu (high share, stable)
    - Karnataka (high share, stable)
    - UP-UK (high share, positive momentum)
    - West Bengal (high share, stable)
  
  Recover: 4 markets
    - Andhra Pradesh (high share, weak momentum)
    - Madhya Pradesh (declining but recoverable)
    - Punjab (declining but recoverable)
    - Haryana (declining but recoverable)
  
  Hold: 3 markets
    - Odisha (stable, medium share)
    - Chhattisgarh (stable, medium share)
    - Jharkhand (stable, medium share)

Notes:
- "Conditional market filtering applied: 3 markets matched the specified criteria from your prompt."
- "Primary anchor metric 'Change in Market Share' was detected from your intent."
```

**Solution:** Only the 3 markets actually losing share got "increase" action. Others kept their intelligence-based actions.

---

## Example 2: High CPR Markets

### Prompt
```
Reduce spend in markets with high CPR and focus on efficient markets
```

### BEFORE FIX ❌
```
Action Summary:
  Decrease: 12 markets (all markets)
  
Notes:
- "Global action preference 'decrease' applied to all markets."
```

**Problem:** ALL markets got "decrease" even though only some had high CPR.

---

### AFTER FIX ✅
```
Action Summary:
  Decrease: 4 markets
    - Rajasthan (CPR: ₹850, high_cost band)
    - Madhya Pradesh (CPR: ₹820, high_cost band)
    - Bihar (CPR: ₹780, high_cost band)
    - Jharkhand (CPR: ₹760, high_cost band)
  
  Increase: 5 markets
    - Maharashtra (CPR: ₹420, low_cost band, high elasticity)
    - Karnataka (CPR: ₹450, low_cost band, high elasticity)
    - Tamil Nadu (CPR: ₹480, low_cost band, high elasticity)
    - Gujarat (CPR: ₹490, low_cost band, high elasticity)
    - UP-UK (CPR: ₹510, low_cost band, high elasticity)
  
  Hold: 3 markets
    - Kerala (CPR: ₹580, mid_cost band)
    - West Bengal (CPR: ₹590, mid_cost band)
    - Andhra Pradesh (CPR: ₹600, mid_cost band)

Notes:
- "Conditional market filtering applied: 4 markets matched high CPR criteria."
- "Efficiency-focused markets were prioritized for increase based on low CPR and high responsiveness."
```

**Solution:** Only high-CPR markets got "decrease". Efficient markets got "increase". Others kept default actions.

---

## Example 3: Gaining Share (Protect Winners)

### Prompt
```
Protect markets where I am gaining market share
```

### BEFORE FIX ❌
```
Action Summary:
  Protect: 12 markets (all markets)
```

**Problem:** Protected ALL markets, even those losing share.

---

### AFTER FIX ✅
```
Action Summary:
  Protect: 6 markets
    - Maharashtra (share change: +3.2%)
    - UP-UK (+2.8%)
    - Karnataka (+2.1%)
    - Tamil Nadu (+1.5%)
    - Gujarat (+0.9%)
    - West Bengal (+0.7%)
  
  Recover: 3 markets
    - Kerala (share change: -2.3%, high share base)
    - Andhra Pradesh (-1.8%, high share base)
    - Rajasthan (-0.9%, medium share)
  
  Hold: 3 markets
    - Odisha (share change: 0.0%)
    - Chhattisgarh (+0.1%, neutral)
    - Jharkhand (-0.1%, neutral)

Notes:
- "Conditional market filtering applied: 6 markets matched the specified criteria from your prompt."
```

**Solution:** Only markets with positive share change got "protect". Declining markets got "recover" to fix them.

---

## Example 4: Explicit Market Names (Still Works!)

### Prompt
```
Increase in Maharashtra and Kerala, protect Tamil Nadu
```

### BEFORE FIX ✅ (Already worked)
```
Action Summary:
  Increase: 2 markets
    - Maharashtra
    - Kerala
  
  Protect: 1 market
    - Tamil Nadu
  
  Hold: 9 markets (all others)
```

### AFTER FIX ✅ (Still works)
```
Action Summary:
  Increase: 2 markets
    - Maharashtra
    - Kerala
  
  Protect: 1 market
    - Tamil Nadu
  
  Recover: 3 markets (intelligence-based)
    - Gujarat
    - Rajasthan
    - Andhra Pradesh
  
  Hold: 6 markets (intelligence-based)
    - Karnataka, UP-UK, West Bengal, Odisha, Chhattisgarh, Jharkhand

Notes:
- "Explicit market instructions from the prompt were given precedence over inferred rankings."
```

**Solution:** Explicit names still work perfectly. Other markets now get smarter intelligence-based actions instead of all "hold".

---

## Example 5: Complex Multi-Condition

### Prompt
```
Increase in markets where I am losing share. Protect markets where I am gaining share. Reduce spend where CPR is high.
```

### BEFORE FIX ❌
```
Action Summary:
  Increase: 12 markets (all markets - last action wins)
```

**Problem:** Only the last action was applied to all markets.

---

### AFTER FIX ✅
```
Action Summary:
  Increase: 2 markets
    - Kerala (losing share: -2.3%)
    - Rajasthan (losing share: -0.9%)
  
  Protect: 5 markets
    - Maharashtra (gaining share: +3.2%)
    - UP-UK (gaining share: +2.8%)
    - Karnataka (gaining share: +2.1%)
    - Tamil Nadu (gaining share: +1.5%)
    - West Bengal (gaining share: +0.7%)
  
  Decrease: 3 markets
    - Madhya Pradesh (high CPR: ₹820)
    - Bihar (high CPR: ₹780)
    - Jharkhand (high CPR: ₹760)
  
  Hold: 2 markets
    - Odisha (neutral on all criteria)
    - Chhattisgarh (neutral on all criteria)

Notes:
- "Conditional market filtering applied: 10 markets matched the specified criteria from your prompt."
- "Multiple conditions were detected and applied to different market segments."
```

**Solution:** Each condition correctly filtered and applied actions to the appropriate markets!

---

## Key Improvements Summary

1. ✅ **Conditional logic now works** - "where" clauses are parsed and applied
2. ✅ **Selective targeting** - Only matching markets get the specified action
3. ✅ **Smarter defaults** - Non-matching markets use intelligence-based actions
4. ✅ **Better explanations** - Notes clearly show what filtering was applied
5. ✅ **Backward compatible** - Explicit market names and global actions still work
6. ✅ **Re-resolve button** - Can retry resolution without losing the prompt

---

## Date: 2026-04-21
