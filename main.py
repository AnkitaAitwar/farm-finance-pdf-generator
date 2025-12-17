from flask import Flask, render_template, request, send_file
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from datetime import datetime
from io import BytesIO
import matplotlib.pyplot as plt
import os

app = Flask(__name__)

# Ensure reports folder exists
if not os.path.exists("reports"):
    os.makedirs("reports")

# ----------------- Utility Functions -----------------
def get_form_data(request):
    """Extracts form data and returns farmer info, expenses, incomes"""
    farmer = request.form.get("farmer")
    crop = request.form.get("crop")
    season = request.form.get("season")
    acres = float(request.form.get("acres") or 0)
    sowing_date = request.form.get("sowing_date")
    harvest_date = request.form.get("harvest_date")
    location = request.form.get("location")

    # Expenses
    exp_categories = request.form.getlist("exp_category[]")
    exp_amounts = request.form.getlist("exp_amount[]")
    exp_dates = request.form.getlist("exp_date[]")
    exp_descs = request.form.getlist("exp_desc[]")
    expenses = []
    for i in range(len(exp_categories)):
        if exp_categories[i]:
            expenses.append({
                "category": exp_categories[i],
                "amount": float(exp_amounts[i] or 0),
                "date": exp_dates[i],
                "desc": exp_descs[i]
            })

    # Incomes
    inc_categories = request.form.getlist("inc_category[]")
    inc_amounts = request.form.getlist("inc_amount[]")
    inc_dates = request.form.getlist("inc_date[]")
    inc_descs = request.form.getlist("inc_desc[]")
    incomes = []
    for i in range(len(inc_categories)):
        if inc_categories[i]:
            incomes.append({
                "category": inc_categories[i],
                "amount": float(inc_amounts[i] or 0),
                "date": inc_dates[i],
                "desc": inc_descs[i]
            })

    return (farmer, crop, season, acres, sowing_date, harvest_date, location, expenses, incomes)

def calculate_summary(expenses, incomes, acres):
    total_expense = sum(item['amount'] for item in expenses)
    total_income = sum(item['amount'] for item in incomes)
    profit = total_income - total_expense
    cost_per_acre = total_expense / acres if acres else 0
    return total_income, total_expense, profit, cost_per_acre

def generate_chart(total_income, total_expense, profit):
    fig, ax = plt.subplots()
    categories_chart = ['Total Income', 'Total Expense', 'Profit/Loss']
    values_chart = [total_income, total_expense, profit]
    ax.bar(categories_chart, values_chart, color=['green','red','blue'])
    ax.set_title('Finance Overview')
    ax.set_ylabel('Amount (₹)')
    img_buffer = BytesIO()
    plt.savefig(img_buffer, format='PNG')
    plt.close(fig)
    img_buffer.seek(0)
    return img_buffer

def create_ledger(expenses, incomes):
    ledger = []
    for e in expenses:
        ledger.append({
            "date": e["date"],
            "particulars": e["category"],
            "type": "Expense",
            "desc": e["desc"],
            "amount": e["amount"]
        })
    for i in incomes:
        ledger.append({
            "date": i["date"],
            "particulars": i["category"],
            "type": "Income",
            "desc": i["desc"],
            "amount": i["amount"]
        })
    return sorted(ledger, key=lambda x: x["date"])

def create_pdf(farmer, crop, season, acres, expenses, incomes, total_income, total_expense, profit, cost_per_acre, chart_img, ledger, filepath):
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, "GramIQ Farm Finance Report")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 70, f"Farmer: {farmer}")
    c.drawString(50, height - 85, f"Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M')}")

    # Finance Summary
    y = height - 130
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Finance Summary")
    c.setFont("Helvetica", 10)
    y -= 20
    c.drawString(50, y, f"Total Income: ₹ {total_income}")
    y -= 15
    c.drawString(50, y, f"Total Expense: ₹ {total_expense}")
    y -= 15
    c.drawString(50, y, f"Profit / Loss: ₹ {profit}")
    y -= 15
    c.drawString(50, y, f"Cost per Acre: ₹ {cost_per_acre:.2f}")

    # Chart
    y -= 40
    chart = ImageReader(chart_img)
    c.drawImage(chart, 50, y-150, width=400, height=150)
    y -= 160

    # Function to draw table
    def draw_table(title, data, columns):
        nonlocal y
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, title)
        y -= 20
        table_data = [columns]
        for row in data:
            table_data.append([str(row[col]) for col in columns])
        table = Table(table_data, colWidths=[100]*len(columns))
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
            ('ALIGN',(0,0),(-1,-1),'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('FONTNAME', (0,0),(-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),10),
        ]))
        table.wrapOn(c, width, height)
        table.drawOn(c, 50, y - 15*len(table_data))
        y -= 15*len(table_data) + 20

    # Draw tables
    draw_table("Expense Breakdown", expenses, ["category","amount","date","desc"])
    draw_table("Income Breakdown", incomes, ["category","amount","date","desc"])
    draw_table("Ledger (Income + Expense)", ledger, ["date","particulars","type","desc","amount"])

    # Footer
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(width / 2, 40, "Proudly maintained accounting with GramIQ")
    c.save()


# ----------------- Flask Routes -----------------
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        try:
            farmer, crop, season, acres, sowing_date, harvest_date, location, expenses, incomes = get_form_data(request)
            total_income, total_expense, profit, cost_per_acre = calculate_summary(expenses, incomes, acres)
            chart_img = generate_chart(total_income, total_expense, profit)
            ledger = create_ledger(expenses, incomes)
            report_filename = f"{crop}_{int(acres)}_{season}_{datetime.now().year}.pdf"
            filepath = f"reports/{report_filename}"
            create_pdf(farmer, crop, season, acres, expenses, incomes, total_income, total_expense, profit, cost_per_acre, chart_img, ledger, filepath)
            return send_file(filepath, as_attachment=True)
        except Exception as e:
            return f"Error generating PDF: {e}"
    return render_template("form.html")


if __name__ == "__main__":
    app.run(debug=True)
