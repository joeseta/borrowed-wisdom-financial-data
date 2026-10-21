# Borrowed Wisdom — Phase 2: Financial Data Integration

A separate Streamlit prototype for testing a **category-summary CSV** interface. It leaves the original Borrowed Wisdom demonstration unchanged.

## Safety and scope

**This GitHub repository and its Streamlit deployment are public. Use only fictional data.** Do not upload real personal or family reports. Even without merchant names, category totals can be sensitive. This prototype intentionally has no database, file writes, external API calls, or automatic AI review; public hosting may still retain operational logs or temporary uploaded content.

The user reviews/corrects their accounting data separately (optionally assisted by ChatGPT). Borrowed Wisdom consumes category summaries; it does not review raw transactions or modify accounting records.

## CSV format

Four columns exactly as the Simplifi Monthly Money Review → Summary → Category → Month → CSV Flat export:

```csv
Income/Expense,Category,Month,Amount
Income,Personal Income: Paycheck,January,3000
Expense,Dining & Drinks: Restaurants,January,-460
```

Expense rows normally have negative amounts. Positive expenses are treated as refunds/credits; flag for review. Reports grouped by Day or Year are not accepted in this prototype.

## Run locally

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Or deploy `app.py` from this repository to Streamlit Community Cloud using the `main` branch. Try the built-in fictional data first.

## Current limitations

- Month names without a year cannot distinguish January of different years; this prototype assumes a single reporting year per CSV.
- No checking/savings balances, card balances, upcoming due dates, or recurring-payment forecast.
- No transaction categorization, reconciliation, AI calls, storage, or background monitoring.
- Results are preliminary historical summaries, **not** individualized financial advice.
