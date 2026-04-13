from fpdf import FPDF

class TaxPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "Canada Tax AI - 2025 Tax Report", align="C")
        self.ln(10)

def generate_tax_pdf(result: dict, filename: str = "tax_report.pdf"):
    pdf = TaxPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, f"Gross Income: ${result['gross_income']:,.2f}", ln=1)
    pdf.cell(0, 10, f"Taxable Income: ${result['taxable_income']:,.2f}", ln=1)
    pdf.cell(0, 10, f"Federal Tax: ${result['federal_tax']:,.2f}", ln=1)
    pdf.cell(0, 10, f"Manitoba Tax: ${result['provincial_tax']:,.2f}", ln=1)
    pdf.cell(0, 10, f"Total Tax: ${result['total_tax']:,.2f}", ln=1)
    pdf.cell(0, 10, f"Estimated Refund/Owing: ${result['estimated_refund_owing']:,.2f}", ln=1)
    pdf.output(filename)
    return filename