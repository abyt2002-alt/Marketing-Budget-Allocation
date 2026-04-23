# "Smaller Markets" Prompt - Expected Behavior

## Your Data (Market Share)
```
Assam-NE:          12%  ← SMALLEST
Delhi-NCR:         29%
Karnataka:         30%
Maharashtra:       31%
Bihar-Jharkhand:   33%
UP-UK:             37%
Gujarat:           40%
Tamil Nadu:        41%
West Bengal:       41%
Rajasthan:         41%
MP-Chhattisgarh:   42%
Odisha:            54%
PunHarHPJK:        56%
Andhra-Telangana:  59%
Kerala:            68%  ← BIGGEST
```

## Your Prompt
```
I want to grow my presence in smaller markets
```

## What Should Happen ✅

The system should:
1. Calculate the median market share (41%)
2. Filter for markets BELOW median (lower 50%)
3. Apply "increase" action ONLY to those markets

### Expected Result:
```
INCREASE: 7 markets (lower 50% by market share)

Assam-NE
Matched your criteria: smaller market with 12.0% share

Delhi-NCR
Matched your criteria: smaller market with 29.0% share

Karnataka
Matched your criteria: smaller market with 30.0% share

Maharashtra
Matched your criteria: smaller market with 31.0% share

Bihar-Jharkhand
Matched your criteria: smaller market with 33.0% share

UP-UK
Matched your criteria: smaller market with 37.0% share

Gujarat
Matched your criteria: smaller market with 40.0% share
```

### Other Markets (upper 50%):
- Tamil Nadu, West Bengal, Rajasthan, MP-Chhattisgarh, Odisha, PunHarHPJK, Andhra-Telangana, Kerala
- Should get intelligence-based actions (protect/hold/recover)

---

## Alternative Prompts That Work

### 1. Bigger Markets
```
I want to focus on bigger markets
```
→ Filters upper 50% by market share (Kerala, Andhra-Telangana, PunHarHPJK, etc.)

### 2. Low Salience Markets
```
I want to grow in markets with low salience
```
→ Filters lower 50% by average of category + brand salience

### 3. High Salience Markets
```
I want to invest in high salience markets
```
→ Filters upper 50% by average of category + brand salience

### 4. Declining Markets
```
I want to recover markets where I'm losing share
```
→ Filters markets with negative "Change in market share"

### 5. Growing Markets
```
I want to protect markets where I'm gaining share
```
→ Filters markets with positive "Change in market share"

---

## How the Filtering Works

### Market Share (Smaller/Bigger)
- Collects all market share values
- Sorts them
- Splits at median (50th percentile)
- Lower half = "smaller markets"
- Upper half = "bigger markets"

### Salience (Low/High)
- Calculates average of category salience + brand salience
- Sorts by average
- Splits at median
- Lower half = "low salience"
- Upper half = "high salience"

### Share Change (Losing/Gaining)
- Uses the "Change in market share" band
- Negative bands (mild_negative, strong_negative) = "losing"
- Positive bands (mild_positive, strong_positive) = "gaining"

---

## Date: 2026-04-21
