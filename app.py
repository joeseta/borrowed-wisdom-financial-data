"""Borrowed Wisdom — Phase 2, category-summary CSV prototype.

No databases, file writes, external services or AI calls. Intended for fictional data
on public hosting; the hosting platform may still collect operational logs.
"""
from __future__ import annotations

import calendar
import io
import hashlib
import re
from datetime import date

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Borrowed Wisdom | Financial Data", page_icon="🧭", layout="centered")

st.markdown("""<style>
html,body,[class*="css"] {font-family: Arial, sans-serif;}
.block-container {max-width: 900px; padding-top: 2rem;}
h1,h2,h3 {color:#0b2349;}
div.stButton > button {border: 1.5px solid #194f94; color:#194f94; font-weight:600;}
.smallprint {color:#65758b; font-size:0.88rem;}
</style>""", unsafe_allow_html=True)

st.title("🧭 Borrowed Wisdom")
st.caption("Phase 2 · Financial data bridge · Version 1.2 · Fictional examples only")
st.warning("Public demonstration. Upload only **fictional category-summary CSV files**. Do not upload real personal or family financial data.")

DEMO = """Income/Expense,Category,Month,Amount
Income,Personal Income: Paycheck,January,3000
Expense,Housing: Rent,January,-1300
Expense,Groceries,January,-410
Expense,Dining & Drinks: Restaurants,January,-460
Expense,Shopping,January,-350
Expense,Utilities,January,-180
Expense,Transportation,January,-200
Expense,Other expenses,January,-240
Income,Personal Income: Paycheck,February,3000
Expense,Housing: Rent,February,-1300
Expense,Groceries,February,-420
Expense,Dining & Drinks: Restaurants,February,-500
Expense,Shopping,February,-360
Expense,Utilities,February,-180
Expense,Transportation,February,-220
Expense,Other expenses,February,-250
Income,Personal Income: Paycheck,March,3000
Expense,Housing: Rent,March,-1300
Expense,Groceries,March,-430
Expense,Dining & Drinks: Restaurants,March,-540
Expense,Shopping,March,-380
Expense,Utilities,March,-180
Expense,Transportation,March,-220
Expense,Other expenses,March,-260
"""

MONTHS = {name.casefold(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name[:3].casefold(): i for i, name in enumerate(calendar.month_name) if name})

def month_number(value: str) -> int | None:
    s = str(value).strip().casefold()
    return MONTHS.get(s)


def parse_amount(value) -> float:
    s = str(value).strip().replace(",", "").replace("$", "").replace("−", "-")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    return float(s)


def read_summary(source) -> tuple[pd.DataFrame, list[str]]:
    frame = pd.read_csv(source, dtype=str, encoding="utf-8-sig").fillna("")
    expected = ["Income/Expense", "Category", "Month", "Amount"]
    if not all(c in frame.columns for c in expected):
        raise ValueError("This isn't the expected Simplifi monthly summary. Required columns: " + ", ".join(expected))
    if any(c in frame.columns for c in ("Payee", "Account", "Notes", "Date")):
        raise ValueError("This looks like transaction-level data. Export a category Summary instead.")
    if frame.empty:
        raise ValueError("The file has no rows.")
    if len(frame) > 10000:
        raise ValueError("This prototype accepts up to 10,000 category-summary rows.")
    frame = frame[expected].copy()
    frame["kind"] = frame["Income/Expense"].str.strip().str.casefold().map({
        "income": "Income", "expense": "Expense", "expenses": "Expense"})
    bad_kind = frame["kind"].isna()
    if bad_kind.any():
        raise ValueError(f"{bad_kind.sum()} rows have an unrecognized Income/Expense label.")
    if (frame["Category"].str.strip() == "").any():
        raise ValueError("Some rows have no category.")
    frame["month_num"] = frame["Month"].map(month_number)
    if frame["month_num"].isna().any():
        raise ValueError("This export must be grouped by Month (January, February, etc.), not Day or Year.")
    try:
        frame["value"] = frame["Amount"].map(parse_amount)
    except ValueError as exc:
        raise ValueError("At least one Amount cannot be read as a number.") from exc
    if (~frame["value"].map(lambda x: abs(x) < float("inf"))).any():
        raise ValueError("Amount contains an invalid value.")
    # Simplifi expenses are signed negative; a positive expense is a credit/refund.
    # Keep credits in the net expense total rather than silently turning them into costs.
    frame["signed"] = frame["value"]
    # For expenses: positive amounts reduce expenses; negative amounts add expenses.
    # Income-like negative corrections may exist: flag rather than quietly sign-flip.
    flags = []
    if ((frame["kind"] == "Income") & (frame["value"] < 0)).any():
        flags.append("Negative income adjustments were detected. Confirm these figures in your financial software.")
    if ((frame["kind"] == "Expense") & (frame["value"] > 0)).any():
        flags.append("Some expense categories contain positive credits/refunds. Confirm how they should affect spending.")
    if frame["Category"].str.contains(r"transfer|tax|fee|insurance|interest", case=False, regex=True).any():
        flags.append("Some categories may represent transfers, taxes, interest, or irregular bills. Monthly totals aren't automatically recurring forecasts.")
    return frame, flags

source_choice = st.radio("Choose your data", ["Try fictional data", "Upload a fictional CSV"], horizontal=True)
if source_choice == "Try fictional data":
    source = io.StringIO(DEMO)
    st.download_button("Download fictional sample CSV", DEMO, file_name="fictional_simplifi_summary.csv", mime="text/csv")
else:
    upload = st.file_uploader("Choose a category-summary CSV", type=["csv"], help="Fictional data only. No individual transactions.")
    if upload is None:
        st.info("Choose a fictional CSV with Income/Expense, Category, Month, and Amount columns.")
        st.stop()
    if upload.size > 2_000_000:
        st.error("Please use a file smaller than 2 MB.")
        st.stop()
    source = io.BytesIO(upload.getvalue())

try:
    df, flags = read_summary(source)
except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
    st.error(str(exc))
    st.stop()

st.subheader("Where do I stand?")
monthly = df.groupby(["month_num", "kind"])["signed"].sum().unstack(fill_value=0)
for col in ("Income", "Expense"):
    if col not in monthly:
        monthly[col] = 0.0
monthly["Spending"] = -monthly["Expense"]
monthly["Difference"] = monthly["Income"] - monthly["Spending"]
monthly = monthly.sort_index()
monthly.index = [calendar.month_name[int(i)] for i in monthly.index]
monthly.index.name = "Month"

show = monthly[["Income", "Spending", "Difference"]].copy()
# Use the same financial colors throughout Borrowed Wisdom.
def difference_color(value):
    if value < -0.005:
        return "color: #b91c1c; font-weight: 700;"
    if value > 0.005:
        return "color: #15803d; font-weight: 700;"
    return "color: #334155; font-weight: 600;"

st.dataframe(
    show.style.format("${:,.2f}").apply(lambda column: column.map(difference_color), subset=["Difference"]),
    use_container_width=True,
)

latest = monthly.iloc[-1]
month = monthly.index[-1]
if latest["Difference"] < 0:
    st.error(f"**{month}: You spent ${-latest['Difference']:,.0f} more than you earned.**")
    st.markdown(f"**What do I need to do today?** Review spending categories and find at least **${-latest['Difference']:,.0f}** to reduce or cover with reliable income. This is a historical result, not a future forecast.")
else:
    st.success(f"**{month}: Your reported income covered your spending, with ${latest['Difference']:,.0f} remaining.**")
    st.markdown("**What do I need to do today?** Check upcoming bills before deciding this money is available to spend.")

# This action planner only uses category totals, never transaction-level data.
# Display suggestions without selecting them for the person.
if latest["Difference"] < 0:
    with st.expander("Help me spend less", expanded=False):
        latest_number = int(next(i for i, name in enumerate(calendar.month_name) if name == month))
        recent = df[(df["kind"] == "Expense") & (df["month_num"] == latest_number)].copy()
        recent["net_spend"] = -recent["signed"]
        by_category = recent.groupby("Category", as_index=False)["net_spend"].sum()
        optional_pattern = r"restaurant|dining|bar|entertainment|shopping|clothing|subscriptions?|coffee|takeout|fast food|travel|recreation|hobbies|wine"
        optional = by_category[by_category["Category"].str.contains(optional_pattern, case=False, regex=True)]
        optional = optional[optional["net_spend"] > 0].sort_values("net_spend", ascending=False).head(8)
        target = max(0.0, float(-latest["Difference"]))
        st.markdown(f"**You need to find ${target:,.0f}. Start with spending you can control.**")
        if optional.empty:
            st.info("No clearly optional categories were identified. Review your spending categories in your accounting software.")
        else:
            st.caption("Choose what you'll reduce. Nothing is selected for you. Amounts are plans, not money already saved.")
            # A fingerprint scopes the temporary on-screen choices to this file and month.
            fingerprint = hashlib.sha256(df[["Income/Expense", "Category", "Month", "Amount"]].to_csv(index=False).encode()).hexdigest()[:12]
            total_savings = 0.0
            for idx, row in optional.iterrows():
                category = str(row["Category"])
                maximum = round(float(row["net_spend"]), 2)
                suffix = hashlib.sha256(category.encode()).hexdigest()[:10]
                key_base = f"cut_{fingerprint}_{month}_{suffix}"
                check_key = key_base + "_yes"
                amount_key = key_base + "_amount"
                if check_key not in st.session_state:
                    st.session_state[check_key] = False
                if amount_key not in st.session_state:
                    st.session_state[amount_key] = 0.0
                st.session_state[amount_key] = max(0.0, min(maximum, float(st.session_state[amount_key])))
                label_col, amount_col, all_col = st.columns([4, 3, 1], vertical_alignment="bottom")
                with label_col:
                    chosen = st.checkbox(f"{category} — ${maximum:,.0f} spent", key=check_key)
                with amount_col:
                    reduction = st.number_input("Reduce by ($)", min_value=0.0, max_value=maximum, step=10.0, key=amount_key, label_visibility="visible", disabled=not chosen)
                with all_col:
                    if st.button("All", key=key_base + "_all", help=f"Reduce all ${maximum:,.0f} from {category}"):
                        st.session_state[check_key] = True
                        st.session_state[amount_key] = maximum
                        st.rerun()
                if chosen:
                    total_savings += reduction
            remaining = max(0.0, target - total_savings)
            first, second = st.columns(2)
            first.metric("You plan to spend less", f"${total_savings:,.0f}/month")
            second.metric("Still need to find", f"${remaining:,.0f}/month")
            if remaining > 0.005:
                st.warning(f"Your selected reductions leave ${remaining:,.0f} to find. You cannot keep spending more than you earn.")
            else:
                st.success("Your selected cuts could cover the reported shortage. Now put the changes into action.")
            st.caption("Based on the latest reported month's spending only. Check whether expenses and income are recurring before treating this as a monthly plan.")

st.subheader("Money coming in vs. money going out")
plot = monthly[["Income", "Spending"]].copy()
plot.index.name = "Month"
st.bar_chart(plot, color=["#16a34a", "#dc2626"], stack=False)

with st.expander("Show spending by category"):
    expenses = df[df["kind"] == "Expense"].copy()
    if expenses.empty:
        st.info("No expense rows in this file.")
    else:
        categories = (expenses.groupby("Category")["signed"].sum() * -1).sort_values(ascending=False)
        st.dataframe(categories.rename("Net spending ($)").to_frame().style.format("${:,.2f}"), use_container_width=True)

if flags:
    with st.expander("Things to check in your accounting software"):
        for flag in flags:
            st.write("• " + flag)

st.caption("These are historical category totals, not verified account balances, upcoming bills, or a prediction. Review and correct records in the accounting platform before relying on them.")
st.caption("No database or intentional file saving is used by this prototype. Public hosting may retain temporary uploads or operational logs. Never upload real financial information to this public demo.")
