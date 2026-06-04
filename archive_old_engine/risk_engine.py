# core/risk_engine.py

class RiskEngine:

    @staticmethod
    def compute_risk(volatility, drawdown):
        score = abs(volatility) * 0.6 + abs(drawdown) * 0.4

        if score < 2:
            level = "Low"
        elif score < 5:
            level = "Medium"
        else:
            level = "High"

        return round(score, 2), level