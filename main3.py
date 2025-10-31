import pandas as pd

pd.set_option('display.max_rows', None)

df = pd.read_excel('balancete-1.xlsx', sheet_name='Table 4', skiprows=1)
df = df.drop(columns=['Unnamed: 3'])
print(df)
