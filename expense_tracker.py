import streamlit as st
import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt
import os
import json
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Configuration ---
DATA_DIR = "user_data"
os.makedirs(DATA_DIR, exist_ok=True)

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# --- Helper Functions ---
def get_user_id(email_or_phone):
    return email_or_phone.replace("@", "_at_").replace(".", "_dot_").replace("+", "_plus_")

def load_expense_data(user_id):
    file_path = os.path.join(DATA_DIR, f"expenses_{user_id}.csv")
    if os.path.exists(file_path):
        return pd.read_csv(file_path, parse_dates=["Date"])
    return pd.DataFrame(columns=["Date", "Category", "Amount", "Note"])

def save_expense_data(user_id, df):
    df.to_csv(os.path.join(DATA_DIR, f"expenses_{user_id}.csv"), index=False)

def load_budget_data(user_id):
    file_path = os.path.join(DATA_DIR, f"budgets_{user_id}.json")
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return {}

def save_budget_data(user_id, budgets):
    with open(os.path.join(DATA_DIR, f"budgets_{user_id}.json"), "w") as f:
        json.dump(budgets, f)

def send_otp_email(recipient, otp):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = recipient
    msg["Subject"] = "\U0001f512 Your OTP for Streamlit Expense Tracker"
    body = f"Your One-Time Password (OTP) is: {otp}\n\nIt will expire in 3 minutes."
    msg.attach(MIMEText(body, "plain"))
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    server.send_message(msg)
    server.quit()

# --- UI Setup ---
st.set_page_config(page_title="💰 Daily Expense Tracker", layout="wide")
st.title("💰 Daily Expense Tracker")

# --- Initialize Session State ---
for key in ["otp_sent", "actual_otp", "logged_in", "user_id", "user_email"]:
    if key not in st.session_state:
        st.session_state[key] = None

# --- Login with Gmail OTP ---
st.sidebar.header("🔐 Login")

if not st.session_state.logged_in:
    email = st.sidebar.text_input("Enter your Gmail address")
    if st.sidebar.button("Send OTP") and email:
        otp = str(random.randint(100000, 999999))
        st.session_state.actual_otp = otp
        st.session_state.user_id = get_user_id(email)
        st.session_state.user_email = email
        send_otp_email(email, otp)
        st.session_state.otp_sent = True
        st.success("✅ OTP sent to your Gmail!")

    if st.session_state.otp_sent:
        user_otp = st.sidebar.text_input("Enter OTP", max_chars=6)
        if st.sidebar.button("Verify OTP"):
            if user_otp == st.session_state.actual_otp:
                st.session_state.logged_in = True
                st.session_state.expenses = load_expense_data(st.session_state.user_id)
                st.session_state.budgets = load_budget_data(st.session_state.user_id)
                st.success("🔓 Logged in successfully!")
            else:
                st.error("❌ Incorrect OTP. Please try again.")
else:
    st.sidebar.markdown(f"**Logged in as:** {st.session_state.user_email}")
    if st.sidebar.button("🚪 Logout"):
        for key in ["logged_in", "otp_sent", "actual_otp", "user_id", "user_email", "expenses", "budgets"]:
            st.session_state[key] = None
        st.experimental_rerun()

if st.session_state.logged_in:
    user_id = st.session_state.user_id
    df_expenses = st.session_state.expenses

    current_hour = dt.datetime.now().hour
    greet = "Good morning ☀️" if current_hour < 12 else "Good afternoon 🌤️" if current_hour < 18 else "Good evening 🌙"
    st.header(f"{greet}, let's track your expenses!")

    st.subheader("🧾 Add a New Expense")
    with st.form("expense_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 When did you spend?", dt.date.today())
        with col2:
            category = st.selectbox("📂 What was it for?", ["Food", "Travel", "Shopping", "Bills", "Entertainment", "Other"])
        amount = st.number_input("💸 How much did you spend? (₹)", min_value=0.0, format="%.2f", step=10.0)
        note = st.text_input("🗒️ Add a note (e.g., Lunch with friends)")
        submitted = st.form_submit_button("➕ Save Expense")

    if submitted:
        new_entry = pd.DataFrame([[date, category, amount, note]], columns=df_expenses.columns)
        df_expenses = pd.concat([df_expenses, new_entry], ignore_index=True)
        df_expenses["Date"] = pd.to_datetime(df_expenses["Date"])
        st.session_state.expenses = df_expenses
        save_expense_data(user_id, df_expenses)
        st.success(f"✅ Added ₹{amount:.2f} to '{category}' on {date.strftime('%b %d, %Y')}")

    if not df_expenses.empty:
        df_expenses["Date"] = pd.to_datetime(df_expenses["Date"])
        st.subheader("📅 Filter by Month")
        month_selected = st.selectbox("Choose a month:", sorted(df_expenses["Date"].dt.strftime("%B %Y").unique(), reverse=True))
        df_filtered = df_expenses[df_expenses["Date"].dt.strftime("%B %Y") == month_selected]

        if not df_filtered.empty:
            st.subheader("💰 Set Your Monthly Budget")
            budgets = st.session_state.budgets
            default_budget = budgets.get(month_selected, 1000.0)
            budget_input = st.number_input(f"Set budget for {month_selected} (₹)", min_value=0.0, value=default_budget, step=100.0)
            budgets[month_selected] = budget_input
            save_budget_data(user_id, budgets)

            total_spent = df_filtered["Amount"].sum()
            remaining_budget = budget_input - total_spent
            pct_used = (total_spent / budget_input * 100) if budget_input > 0 else 0

            st.markdown(f"### 💸 You've spent ₹{total_spent:.2f} of ₹{budget_input:.2f}.")
            st.progress(min(100, int(pct_used)))

            if remaining_budget < 0:
                st.error(f"🚨 Over budget by ₹{-remaining_budget:.2f}!")
            elif pct_used > 90:
                st.warning(f"⚠️ You're over 90% of your budget. Only ₹{remaining_budget:.2f} left.")
            else:
                st.success(f"✅ You're within budget! ₹{remaining_budget:.2f} remaining.")

            st.subheader(f"📋 Expenses in {month_selected}")
            df_filtered["Delete"] = False
            edited_df = st.data_editor(df_filtered, num_rows="dynamic", use_container_width=True)

            delete_rows = edited_df[edited_df["Delete"] == True]
            if not delete_rows.empty and st.button("🗑️ Delete Selected Expenses"):
                df_updated = edited_df[edited_df["Delete"] == False].drop(columns=["Delete"])
                st.session_state.expenses = st.session_state.expenses[
                    ~(
                        (st.session_state.expenses["Date"].isin(delete_rows["Date"])) &
                        (st.session_state.expenses["Category"].isin(delete_rows["Category"])) &
                        (st.session_state.expenses["Amount"].isin(delete_rows["Amount"])) &
                        (st.session_state.expenses["Note"].isin(delete_rows["Note"]))
                    )
                ]
                save_expense_data(user_id, st.session_state.expenses)
                st.success(f"Deleted {len(delete_rows)} expense(s).")
                st.rerun()

            if st.button("📂 Save Changes"):
                df_to_save = edited_df.drop(columns=["Delete"])
                mask = st.session_state.expenses["Date"].dt.strftime("%B %Y") == month_selected
                st.session_state.expenses.loc[mask, ["Date", "Category", "Amount", "Note"]] = df_to_save[["Date", "Category", "Amount", "Note"]].values
                save_expense_data(user_id, st.session_state.expenses)
                st.success("✅ Changes saved successfully.")

            st.markdown("**📌 Top Spending Categories:**")
            top_cats = df_filtered.groupby("Category")["Amount"].sum().sort_values(ascending=False)
            for i, (cat, val) in enumerate(top_cats.items()):
                if i >= 3:
                    break
                st.markdown(f"- {cat}: ₹{val:.2f}")

            daily_totals = df_filtered.groupby("Date")["Amount"].sum()
            overspend_days = daily_totals[daily_totals > 500]
            if not overspend_days.empty:
                st.warning("⚠️ You spent more than ₹500 on these days:")
                for date, total in overspend_days.items():
                    st.markdown(f"- **{date.strftime('%b %d')}**: ₹{total:.2f}")

            st.subheader("📊 Where Your Money Went")
            fig1, ax1 = plt.subplots()
            ax1.pie(top_cats, labels=top_cats.index, autopct="%.1f%%", startangle=140)
            ax1.axis("equal")
            st.pyplot(fig1)

            st.subheader("📈 Daily Spending Trend")
            st.line_chart(daily_totals)

            st.download_button("⬇️ Download This Month's Data", df_filtered.to_csv(index=False), file_name="monthly_expenses.csv")

    else:
        st.info("💡 No expenses added yet. Start by entering your first one above!")

else:
    st.warning("👤 Please log in to start tracking your expenses.")

st.markdown("---")
st.markdown("Made with ❤️ using Streamlit | Manage your money. Master your month.")
