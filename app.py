from flask import Flask, render_template, request, redirect, session, flash, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime, timedelta
import calendar
import csv
import os
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = "expense_tracker_secret_key_123"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "database.db")

os.makedirs(INSTANCE_DIR, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + DB_PATH.replace("\\", "/")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================
# Database Models
# =========================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    monthly_budget = db.Column(db.Float, default=0.0)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    t_type = db.Column(db.String(20), nullable=False)  # income / expense
    date = db.Column(db.String(20), nullable=False)    # YYYY-MM-DD
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


with app.app_context():
    db.create_all()


# =========================
# Helpers
# =========================
def parse_date(date_str: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None


def get_filtered_transactions(transactions, filter_range: str):
    today = datetime.today()

    if filter_range == "weekly":
        start_date = today - timedelta(days=6)
        return [
            t for t in transactions
            if (dt := parse_date(t.date)) is not None and dt.date() >= start_date.date()
        ]

    if filter_range == "yearly":
        return [
            t for t in transactions
            if (dt := parse_date(t.date)) is not None and dt.year == today.year
        ]

    # default monthly
    return [
        t for t in transactions
        if (dt := parse_date(t.date)) is not None and dt.month == today.month and dt.year == today.year
    ]


def get_spending_suggestion(total_expense, budget, category_totals):
    if total_expense == 0:
        return "No expenses added yet. Start tracking your spending."

    if not category_totals:
        return "Add expense categories to get better suggestions."

    top_category = max(category_totals, key=category_totals.get)

    if budget > 0:
        budget_left = budget - total_expense
        if budget_left < 0:
            return f"You crossed your monthly budget. Highest spending is in {top_category}."
        if budget_left < budget * 0.2:
            return f"Only a small part of your budget is left. Try reducing spending in {top_category}."
        return f"Your spending is under control. Highest spending is in {top_category}."

    return f"Highest spending is in {top_category}. Try reducing this category to save more."


def get_saving_tip(category_totals, budget_remaining, monthly_budget):
    if "Shopping" in category_totals and category_totals["Shopping"] > 1000:
        return "Your shopping expense is high. Try setting a weekly shopping limit."
    if "Food" in category_totals and category_totals["Food"] > 1500:
        return "Your food expense is rising. Meal planning can help reduce it."
    if monthly_budget > 0 and budget_remaining < monthly_budget * 0.2:
        return "Your remaining budget is low. Keep daily spending limited for the rest of the month."
    if "Travel" in category_totals and category_totals["Travel"] > 1200:
        return "Travel spending is increasing. Try grouping trips to save cost."
    return "Your spending pattern looks balanced. Keep tracking regularly."


def get_prediction_text(total_expense):
    today = datetime.today()
    current_day = today.day
    total_days = calendar.monthrange(today.year, today.month)[1]

    if current_day <= 0:
        return "Not enough data for prediction."

    predicted_month_expense = (total_expense / current_day) * total_days
    return f"At this rate, your total monthly expense may reach ₹{predicted_month_expense:.2f}."


def login_required():
    return "user_id" in session


# =========================
# Routes
# =========================
@app.route("/")
def home():
    if login_required():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not username or not password or not confirm_password:
            flash("Please fill all fields.", "error")
            return redirect(url_for("signup"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("signup"))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists. Please use another username.", "error")
            return redirect(url_for("signup"))

        hashed_password = generate_password_hash(password)
        user = User(username=username, password=hashed_password)

        db.session.add(user)
        db.session.commit()

        flash("Signup successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please enter username and password.", "error")
            return redirect(url_for("login"))

        user = User.query.filter_by(username=username).first()

        if not user:
            flash("Username not found. Please sign up first.", "error")
            return redirect(url_for("login"))

        if not check_password_hash(user.password, password):
            flash("Password is incorrect.", "error")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        session["username"] = user.username
        flash("Login successful.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not username or not new_password or not confirm_password:
            flash("Please fill all fields.", "error")
            return redirect(url_for("reset_password"))

        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("reset_password"))

        user = User.query.filter_by(username=username).first()
        if not user:
            flash("Username not found.", "error")
            return redirect(url_for("reset_password"))

        user.password = generate_password_hash(new_password)
        db.session.commit()

        flash("Password reset successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if not login_required():
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "budget":
            budget_value = request.form.get("monthly_budget", "").strip()
            try:
                user.monthly_budget = float(budget_value)
                db.session.commit()
                flash("Monthly budget updated successfully.", "success")
            except ValueError:
                flash("Enter a valid budget amount.", "error")
            return redirect(url_for("dashboard"))

        if form_type == "transaction":
            title = request.form.get("title", "").strip()
            amount = request.form.get("amount", "").strip()
            date = request.form.get("date", "").strip()
            category = request.form.get("category", "").strip()
            t_type = request.form.get("t_type", "").strip()

            if not title or not amount or not date or not category or not t_type:
                flash("Please fill all transaction fields.", "error")
                return redirect(url_for("dashboard"))

            try:
                amount = float(amount)
            except ValueError:
                flash("Enter a valid amount.", "error")
                return redirect(url_for("dashboard"))

            if amount <= 0:
                flash("Amount must be greater than zero.", "error")
                return redirect(url_for("dashboard"))

            transaction = Transaction(
                title=title,
                amount=amount,
                date=date,
                category=category,
                t_type=t_type,
                user_id=user.id
            )

            db.session.add(transaction)
            db.session.commit()
            flash("Transaction added successfully.", "success")
            return redirect(url_for("dashboard"))

    filter_range = request.args.get("filter", "monthly").lower()
    if filter_range not in ["weekly", "monthly", "yearly"]:
        filter_range = "monthly"

    all_transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.id.desc()).all()
    filtered_transactions = get_filtered_transactions(all_transactions, filter_range)

    total_income = sum(t.amount for t in all_transactions if t.t_type == "income")
    total_expense = sum(t.amount for t in all_transactions if t.t_type == "expense")
    balance = total_income - total_expense
    budget_remaining = user.monthly_budget - total_expense

    spent_percent = 0
    if user.monthly_budget > 0:
        spent_percent = min((total_expense / user.monthly_budget) * 100, 100)

    chart_source = filtered_transactions
    category_totals = {}
    for t in chart_source:
        if t.t_type == "expense":
            category_totals[t.category] = category_totals.get(t.category, 0) + t.amount

    budget_warning = user.monthly_budget > 0 and total_expense > user.monthly_budget
    suggestion = get_spending_suggestion(total_expense, user.monthly_budget, category_totals)
    saving_tip = get_saving_tip(category_totals, budget_remaining, user.monthly_budget)
    prediction_text = get_prediction_text(total_expense)

    return render_template(
        "dashboard.html",
        username=user.username,
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        monthly_budget=user.monthly_budget,
        budget_remaining=budget_remaining,
        spent_percent=spent_percent,
        transactions=all_transactions,
        budget_warning=budget_warning,
        suggestion=suggestion,
        saving_tip=saving_tip,
        prediction_text=prediction_text,
        chart_labels=list(category_totals.keys()),
        chart_values=list(category_totals.values()),
        active_filter=filter_range
    )


@app.route("/delete/<int:txn_id>")
def delete_transaction(txn_id):
    if not login_required():
        return redirect(url_for("login"))

    txn = Transaction.query.get_or_404(txn_id)

    if txn.user_id != session["user_id"]:
        flash("Unauthorized action.", "error")
        return redirect(url_for("dashboard"))

    db.session.delete(txn)
    db.session.commit()
    flash("Transaction deleted successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/download_pdf")
def download_pdf():
    if not login_required():
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user:
        return redirect(url_for("login"))

    transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.id.desc()).all()

    total_income = sum(t.amount for t in transactions if t.t_type == "income")
    total_expense = sum(t.amount for t in transactions if t.t_type == "expense")
    budget_remaining = user.monthly_budget - total_expense

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle("Expense Report")

    y = 800
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, f"Expense Report - {user.username}")
    y -= 30

    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Monthly Budget: Rs. {user.monthly_budget}")
    y -= 20
    pdf.drawString(50, y, f"Total Income: Rs. {total_income}")
    y -= 20
    pdf.drawString(50, y, f"Total Expense: Rs. {total_expense}")
    y -= 20
    pdf.drawString(50, y, f"Budget Left: Rs. {budget_remaining}")
    y -= 30

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Transaction History")
    y -= 25

    pdf.setFont("Helvetica", 10)

    if not transactions:
        pdf.drawString(50, y, "No transactions available.")
    else:
        for txn in transactions:
            line = f"{txn.date} | {txn.title} | {txn.category} | {txn.t_type} | Rs. {txn.amount}"
            pdf.drawString(50, y, line)
            y -= 18
            if y < 50:
                pdf.showPage()
                y = 800
                pdf.setFont("Helvetica", 10)

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="expense_report.pdf",
        mimetype="application/pdf"
    )


@app.route("/export_csv")
def export_csv():
    if not login_required():
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user:
        return redirect(url_for("login"))

    transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.id.desc()).all()

    file_path = os.path.join(BASE_DIR, "instance", "transactions.csv")
    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Date", "Title", "Amount", "Category", "Type"])
        for txn in transactions:
            writer.writerow([txn.date, txn.title, txn.amount, txn.category, txn.t_type])

    return send_file(file_path, as_attachment=True, download_name="transactions.csv")


@app.route("/export_excel")
def export_excel():
    if not login_required():
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user:
        return redirect(url_for("login"))

    transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.id.desc()).all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Transactions"

    sheet.append(["Date", "Title", "Amount", "Category", "Type"])

    for txn in transactions:
        sheet.append([txn.date, txn.title, txn.amount, txn.category, txn.t_type])

    file_path = os.path.join(BASE_DIR, "instance", "transactions.xlsx")
    workbook.save(file_path)

    return send_file(file_path, as_attachment=True, download_name="transactions.xlsx")


if __name__ == "__main__":
    app.run(debug=True)