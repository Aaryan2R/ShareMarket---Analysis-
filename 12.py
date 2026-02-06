import pandas as pd

data = [
    {
        "company_name": "Tata Consultancy Services",
        "last_quarterly": "",
        "last_annual": "",
        "last_price_daily": "2026-01-28",
        "last_price_weekly": "",
        "last_news": "2026-01-28",
        "status": "pending",
        "reports_complete": "False"
    },
    {
        "company_name": "Infosys",
        "last_quarterly": "",
        "last_annual": "",
        "last_price_daily": "2026-01-28",
        "last_price_weekly": "",
        "last_news": "2026-01-28",
        "status": "pending",
        "reports_complete": "False"
    },
    {
        "company_name": "Reliance Industries Ltd",
        "last_quarterly": "",
        "last_annual": "",
        "last_price_daily": "",
        "last_price_weekly": "",
        "last_news": "",
        "status": "pending",
        "reports_complete": "False"
    }
]

df = pd.DataFrame(data)
df.to_csv("data/companies.csv", index=False)

print("companies.csv updated successfully")
