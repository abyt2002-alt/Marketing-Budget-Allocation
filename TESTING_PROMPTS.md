# Intent Interpretation — Testing Prompts

5 available columns:
- `market_share` (level)
- `category_salience` (level)
- `brand_salience` (level)
- `change_in_market_share` (trend: negative = losing, positive = gaining)
- `change_in_brand_equity` (trend: negative = declining, positive = improving)

---

## Tier 1 — Single Step (baseline, should always work)

```
Increase spend in markets that are losing market share
```
```
Focus on markets where brand equity is improving
```
```
Target the top 5 markets by category salience
```
```
Decrease spend in markets where market share is above median
```

---

## Tier 2 — Two Conditions (AND-chained, expect 2 steps)

```
Increase in markets losing market share and where brand salience is below category salience
```
```
Focus on markets where brand equity is declining and market share is below median
```
```
Target markets where category salience is above median and brand salience is below median
```
```
Increase in markets gaining market share and where brand equity is also improving
```

---

## Tier 3 — Three Conditions (main fix target, expect 3 steps)

```
Increase spend in markets losing market share and where brand salience is at or below category salience, but exclude the top 3 markets by category salience
```
```
Focus on markets where brand equity is declining, market share is below median, and brand salience is below category salience
```
```
Target markets that are losing share and have low brand salience, but exclude the top 5 markets by market share
```
```
Increase in markets where brand equity is declining and category salience is high, but exclude the bottom 2 markets by market share
```

---

## Tier 4 — Multi-Segment (two distinct groups, different actions)

```
Increase in markets losing market share, but decrease in markets where market share is above median and brand equity is improving
```
```
For markets where brand salience is below category salience increase spend, for markets where brand salience is above category salience protect spend
```
```
Top 5 markets by category salience should get increased spend, bottom 5 should get decreased spend
```

---

## Prompt wording tips

- Use **"above median" / "below median"** for level metrics — not "high" / "low" (Gemini reads "high X but low Y" as a single comparison, not two filters)
- Use **"losing" / "gaining"** for trend metrics — these map cleanly to `change_in_market_share < 0` and `> 0`
- Use **"exclude the top/bottom N"** for exclusions — clearer than "don't include" or "remove"
- Chain conditions with **"and"** for multi-step single-segment; use **"but decrease / but protect"** to trigger multi-segment

---

## What to check in the UI

| Tier | Expected steps | Pass condition |
|------|---------------|----------------|
| 1 | 1 step | 1 step shown, correct markets matched |
| 2 | 2 steps | Both conditions appear as separate steps |
| 3 | 3 steps | All 3 conditions appear as separate steps |
| 4 | Multi-segment | Two segments shown with correct action per group |
