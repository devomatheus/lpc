import fitz

doc = fitz.open("balancete-1.pdf")
for page in doc:
    print(page.get_text("text"))
