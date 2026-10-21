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
:root{--bw-ink:#14263e;--bw-blue:#174f95;--bw-light:#e9f1fc;}
[data-testid="stAppViewContainer"]{font-family:Arial,Helvetica,sans-serif;color:var(--bw-ink)}
.block-container{max-width:810px;padding-top:2.2rem;padding-bottom:3rem}
h1,h2,h3,p,div,span,label,button{font-family:Arial,Helvetica,sans-serif}
h1{font-size:2rem!important;font-weight:750!important;letter-spacing:-.035em}
h2,h3{font-size:1.3rem!important;font-weight:750!important;letter-spacing:-.02em}
[data-testid="stCaptionContainer"] p{font-size:.81rem;color:#697789}
.stButton>button{min-height:48px!important;border-radius:10px!important;border:2px solid var(--bw-blue)!important;background:var(--bw-light)!important;color:var(--bw-blue)!important;font-size:1rem!important;font-weight:750!important}
.stButton>button[kind="primary"]{background:var(--bw-blue)!important;color:white!important}
[data-testid="stExpander"]{border:1px solid #c8d7e7!important;border-radius:9px!important}
[data-testid="stExpander"] summary{background:#eef4fc;font-weight:700;color:#174f95}
.bw-expense-amount{font-size:1.07rem;text-align:right;padding-right:1.35rem;white-space:nowrap;color:#14263e;}
[data-testid="stCheckbox"] label{font-size:1.04rem!important;}
[data-testid="stNumberInput"] input{font-size:1rem!important;}
@media(max-width:600px){.block-container{padding:1rem 1rem 2rem}h1{font-size:1.7rem!important}.bw-expense-amount{padding-right:.25rem}}
</style>""",unsafe_allow_html=True)

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

def money(n: float) -> str:
    return f"${abs(n):,.0f}"


def change_screen(where: str):
    st.session_state["bw2_screen"] = where


st.title("🧭 Borrowed Wisdom")
st.caption("What do I need to do today?  |  Financial data bridge · Fictional examples")
with st.expander("Choose your financial data", expanded=not st.session_state.get("bw2_data_seen", False)):
    source_choice = st.radio("Choose your data", ["Try fictional data", "Upload a fictional CSV"], horizontal=True)
    st.warning("Public demo: fictional category-summary CSV files only. Never upload real family or personal data here.")
    if source_choice == "Try fictional data":
        source = io.StringIO(DEMO)
        st.download_button("Download fictional sample CSV", DEMO, file_name="fictional_simplifi_summary.csv", mime="text/csv")
    else:
        upload = st.file_uploader("Choose a fictional category-summary CSV",type=["csv"],help="Category totals only; no transactions")
        if upload is None:
            st.info("Select a fictional CSV with Income/Expense, Category, Month and Amount columns.")
            st.stop()
        if upload.size > 2_000_000:
            st.error("Please use a file smaller than 2 MB.")
            st.stop()
        source = io.BytesIO(upload.getvalue())
st.session_state["bw2_data_seen"] = True
try:
    df, flags = read_summary(source)
except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
    st.error(str(exc))
    st.stop()

monthly = df.groupby(["month_num", "kind"])["signed"].sum().unstack(fill_value=0)
for col in ("Income", "Expense"):
    if col not in monthly:
        monthly[col] = 0.0
monthly["Spending"] = -monthly["Expense"]
monthly["Difference"] = monthly["Income"] - monthly["Spending"]
monthly = monthly.sort_index()
monthly.index = [calendar.month_name[int(i)] for i in monthly.index]
monthly.index.name = "Month"
latest = monthly.iloc[-1]
month = monthly.index[-1]
shortfall = max(0., -float(latest["Difference"]))
fingerprint = hashlib.sha256(df[["Income/Expense","Category","Month","Amount"]].to_csv(index=False).encode()).hexdigest()[:12]
latest_number = next(i for i, name in enumerate(calendar.month_name) if name == month)
recent = df[(df["kind"] == "Expense") & (df["month_num"] == latest_number)].copy()
recent["net_spend"] = -recent["signed"]
by_cat = recent.groupby("Category",as_index=False)["net_spend"].sum()
# Show every spending category in the CSV, not just the categories that
# match a discretionary-spending keyword list. The user makes the decision.
spend_categories = by_cat[by_cat["net_spend"] > 0].sort_values(
    "net_spend", ascending=False
).reset_index(drop=True)

# For essential obligations, let the user explore potential future reductions,
# but don't offer the one-click "All" option (which could imply skipping bills).
def essential_category(category: str) -> bool:
    return bool(re.search(r"\b(rent|mortgage|housing|utilities|electric|water|insurance|medical|healthcare|tuition|childcare|loan payment)\b", category, re.I))

# Saved plan keys are NOT widget keys. They persist when a screen is hidden.
def keys(cat):
    digest = hashlib.sha256(cat.encode()).hexdigest()[:12]
    prefix = f"bw2_{fingerprint}_{month}_{digest}"
    return prefix+"_saved_checked",prefix+"_saved_amount",prefix+"_ui_checked",prefix+"_ui_amount"

def keep_choice(cat):
    saved_yes,saved_amt,ui_yes,ui_amt=keys(cat)
    if ui_yes in st.session_state:
        st.session_state[saved_yes]=bool(st.session_state[ui_yes])
    if ui_amt in st.session_state:
        st.session_state[saved_amt]=float(st.session_state[ui_amt])

def all_choice(cat, maximum):
    saved_yes,saved_amt,ui_yes,ui_amt=keys(cat)
    st.session_state[saved_yes]=True
    st.session_state[saved_amt]=maximum
    st.session_state[ui_yes]=True
    st.session_state[ui_amt]=maximum

def total_selected():
    total=0.
    for _,r in spend_categories.iterrows():
        a,b,_,_=keys(str(r["Category"]))
        if st.session_state.get(a,False):
            total += min(float(r["net_spend"]),max(0.,float(st.session_state.get(b,0.))))
    return total

st.session_state.setdefault("bw2_screen","Today")
nav=st.columns(3)
for col,name in zip(nav,["Today","Spend less","See my future"]):
    with col:
        st.button(name,key="bw2_nav_"+name,type="primary" if st.session_state["bw2_screen"]==name else "secondary",use_container_width=True,on_click=change_screen,args=(name,))

view=st.session_state["bw2_screen"]
if view=="Today":
    st.subheader("Where do I stand?")
    if shortfall>0:
        st.error(f"**{month}: You spent {money(shortfall)} more than you earned.**")
    else:
        st.success(f"**{month}: Income covered spending. {money(float(latest['Difference']))} left.**")
    a,b=st.columns(2)
    a.metric("Money coming in",money(float(latest["Income"])))
    b.metric("Money going out",money(float(latest["Spending"])))
    st.subheader("What do I need to do today?")
    if shortfall>0:
        st.markdown(f"**Find a way to spend {money(shortfall)} less or bring in reliable income.**")
        st.button(f"Help me find {money(shortfall)}",type="primary",use_container_width=True,on_click=change_screen,args=("Spend less",))
    else:
        st.markdown("**Check upcoming bills before treating the remaining money as available to spend.**")
    with st.expander("Show the numbers"):
        def diff_style(v):
            return "color:#b91c1c;font-weight:700" if v<-.005 else "color:#15803d;font-weight:700" if v>.005 else "color:#334155"
        st.dataframe(monthly[["Income","Spending","Difference"]].style.format("${:,.2f}").apply(lambda s:s.map(diff_style),subset=["Difference"]),use_container_width=True)
        st.bar_chart(monthly[["Income","Spending"]],color=["#16a34a","#dc2626"],stack=False)
    st.caption("Historical summary only. Account balances, future bills and debt terms are not in this CSV.")
elif view=="Spend less":
    st.subheader("What do I need to do today?")
    if shortfall<=0:
        st.success("The latest month shows no reported shortage. Review future bills before spending what remains.")
    else:
        st.markdown(f"**You need to reduce monthly spending by {money(shortfall)}. Start here.**")
        st.caption("Choose what you’ll stop or reduce. Nothing is selected for you. Essential bills must still be paid unless their cost actually changes.")
        if spend_categories.empty:
            st.info("No expense categories with positive net spending were found in the latest month's summary.")
        else:
            for _,r in spend_categories.iterrows():
                cat=str(r["Category"]); maximum=round(float(r["net_spend"]),2)
                saved_yes,saved_amt,ui_yes,ui_amt=keys(cat)
                st.session_state.setdefault(saved_yes,False)
                st.session_state.setdefault(saved_amt,0.0)
                # Restore widget values when returning to this screen.
                if ui_yes not in st.session_state: st.session_state[ui_yes]=st.session_state[saved_yes]
                if ui_amt not in st.session_state: st.session_state[ui_amt]=min(maximum,float(st.session_state[saved_amt]))
                # Match Phase 1 demo: fixed three-column grid with aligned amounts and controls.
                left, mid, right = st.columns([2.7, 1.3, 2.0], vertical_alignment="center")
                with left:
                    active = st.checkbox(cat, key=ui_yes, on_change=keep_choice, args=(cat,))
                with mid:
                    st.markdown(f'<div class="bw-expense-amount">{money(maximum)}</div>', unsafe_allow_html=True)
                with right:
                    if active:
                        amount_col, all_col = st.columns([3, 1], vertical_alignment="center")
                        with amount_col:
                            st.number_input(
                                f"Spend less on {cat}", min_value=0.0, max_value=maximum,
                                step=10.0, key=ui_amt, label_visibility="collapsed",
                                on_change=keep_choice, args=(cat,)
                            )
                        with all_col:
                            if not essential_category(cat):
                                st.button("All", key=ui_yes+"_all", on_click=all_choice,
                                          args=(cat,maximum), use_container_width=True,
                                          help=f"Stop all {money(maximum)} of this spending")
                            else:
                                st.caption("Review first")
                    else:
                        st.caption("Essential / review first" if essential_category(cat) else "Choose to reduce")
            selected=total_selected()
            remaining=max(0.,shortfall-selected)
            a,b=st.columns(2)
            a.metric("Spend less each month",money(selected))
            b.metric("Still need each month",money(remaining))
            if remaining>0: st.warning(f"**You still need {money(remaining)} each month.**")
            else: st.success("**Your selected reductions cover this month's reported gap. Now follow through.**")
            st.button("See what my cuts change",type="primary",use_container_width=True,on_click=change_screen,args=("See my future",))
    with st.expander("Show spending by category"):
        st.dataframe(by_cat[["Category","net_spend"]].rename(columns={"net_spend":"Net spending ($)"}),use_container_width=True,hide_index=True)
else:
    st.subheader("See my future")
    selected=total_selected()
    after=max(0.,shortfall-selected)
    st.markdown(f"**No changes: {money(shortfall)} monthly gap. With selected cuts: {money(after)} monthly gap.**")
    st.caption("Illustrative only: assumes the latest month's income and spending repeat each month. This is not an account-balance forecast.")
    if shortfall>0:
        import altair as alt
        future=pd.DataFrame({"Months":[3,6,12],"No changes":[shortfall*x for x in (3,6,12)],"With selected cuts":[after*x for x in (3,6,12)]})
        long=future.melt("Months",var_name="Scenario",value_name="Additional money needed")
        chart=alt.Chart(long).mark_bar().encode(x=alt.X("Months:O",title="Months ahead"),xOffset="Scenario:N",y=alt.Y("Additional money needed:Q",title="Additional money needed ($)"),color=alt.Color("Scenario:N",scale=alt.Scale(domain=["No changes","With selected cuts"],range=["#c52332","#168a50"])),tooltip=["Scenario","Months",alt.Tooltip("Additional money needed:Q",format=",.0f")]).properties(height=290)
        st.altair_chart(chart,use_container_width=True)
        st.error(f"**Without changes, you would need {money(shortfall*12)} more over 12 months. Where will you get the money?**")
        st.success(f"**If you make your selected cuts, the 12-month gap becomes {money(after*12)}.**")
        st.button("Go back to spending choices",use_container_width=True,on_click=change_screen,args=("Spend less",))
    else:
        st.success("No monthly gap appears in the latest reported month. We still need balances and upcoming bills to predict your future.")

if flags:
    with st.expander("Items to review in your accounting software"):
        for flag in flags: st.write("• "+flag)
st.caption("Phase 2 · Fictional data only. No linked accounts or transactions; no database or intentional file saving. Public hosting may retain uploads or logs. Do not enter real financial information.")
