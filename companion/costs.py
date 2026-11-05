from .sqlite_utils import open_sqlite
from datetime import datetime
from pathlib import Path

# OpenAI standard short-context text token rates in USD per 1,000,000 tokens,
# verified 2026-11-04. Update this table when provider pricing changes.
PRICES = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-terra": (1.00, 5.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6-astra": (10.00, 50.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    # Upper published peak rates; cached/off-peak tokens may actually cost less.
    "deepseek-flash": (0.30, 1.20),
    "deepseek-v4-pro": (1.32, 3.96),
}


def estimate_text_cost(model, input_tokens, output_tokens, rates=None):
    if rates is None and model not in PRICES:
        raise ValueError(f"Unknown local price for model: {model}; configure explicit input/output rates")
    input_rate, output_rate = PRICES[model] if rates is None else rates
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


class SpendLedger:
    def __init__(self, database_path):
        self.path = str(Path(database_path))
        with open_sqlite(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS api_usage (
                at_local TEXT NOT NULL, model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
                estimated_usd REAL NOT NULL
            )""")

    def record(self, model, input_tokens, output_tokens, rates=None):
        usd = estimate_text_cost(model, input_tokens, output_tokens, rates=rates)
        with open_sqlite(self.path) as db:
            db.execute("INSERT INTO api_usage VALUES (?, ?, ?, ?, ?)",
                       (datetime.now().isoformat(timespec="seconds"), model,
                        input_tokens, output_tokens, usd))
        return usd

    def month_total(self):
        prefix = datetime.now().strftime("%Y-%m")
        with open_sqlite(self.path) as db:
            value = db.execute(
                "SELECT COALESCE(SUM(estimated_usd),0) FROM api_usage WHERE at_local LIKE ?",
                (prefix + "%",),
            ).fetchone()[0]
        return float(value)

    def today_count(self):
        prefix = datetime.now().strftime("%Y-%m-%d")
        with open_sqlite(self.path) as db:
            value = db.execute(
                "SELECT COUNT(*) FROM api_usage WHERE at_local LIKE ?",
                (prefix + "%",),
            ).fetchone()[0]
        return int(value)
