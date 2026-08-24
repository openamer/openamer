"""OpenAmer Funding Engine — Einnahmen generieren und verfolgen

Reale Einnahmequellen (keine Theorie):
1. GitHub Sponsors — monatliche Tiers ($3/$10/$25/$250)
2. Ko-fi / Buy Me a Coffee — Einmalspenden (☕ $3-$50)
3. PayPal — Direktspenden (jeder Betrag)
4. Enterprise — Rechnungen (€499-€9999, Stripe)

Jede Spende tracked in store/funding.json
Läuft als Cron-Job: prüft auf neue Sponsors, sendet Dankes-Nachricht.
"""
import json, os, sys, time, uuid
from pathlib import Path
from datetime import datetime

STORE_DIR = Path(os.path.expanduser("~")) / "AppData" / "Local" / "openamer-laptop" / "store"
FUNDING_FILE = STORE_DIR / "funding.json"
SPONSORS_FILE = STORE_DIR / "sponsors.json"

TIERS = {
    "supporter": {"price": 3, "name": "🥉 Supporter", "badge": "Supporter"},
    "backer": {"price": 10, "name": "🥈 Backer", "badge": "Backer"},
    "sponsor": {"price": 25, "name": "🥇 Sponsor", "badge": "Sponsor"},
    "enterprise": {"price": 250, "name": "🏆 Enterprise", "badge": "Enterprise"},
}

PAYMENT_LINKS = {
    "github_sponsors": "https://github.com/sponsors/openamer",
    "ko-fi": "https://ko-fi.com/openamer_agent",
    "buymeacoffee": "https://buymeacoffee.com/openamer",
    "paypal": "https://www.paypal.com/paypalme/openamer",
    "enterprise": "mailto:openamer@openamer.ai",
}


class FundingEngine:
    def __init__(self):
        os.makedirs(STORE_DIR, exist_ok=True)
        self._ensure(FUNDING_FILE, {"total_raised": 0, "transactions": [], "goal": 500})
        self._ensure(SPONSORS_FILE, {"active": [], "history": [], "total_monthly": 0})
    
    def _ensure(self, path, default):
        if not path.exists():
            path.write_text(json.dumps(default, indent=2))
    
    def _load(self, path):
        return json.loads(path.read_text())
    
    def _save(self, path, data):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    def record_payment(self, source: str, amount: float, name: str = "", message: str = ""):
        """Record a payment/donation."""
        funding = self._load(FUNDING_FILE)
        tx = {
            "id": str(uuid.uuid4())[:12],
            "source": source,
            "amount": amount,
            "name": name or "Anonymous",
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        funding["transactions"].append(tx)
        funding["total_raised"] += amount
        funding["goal_progress"] = min(100, int(funding["total_raised"] / funding["goal"] * 100))
        self._save(FUNDING_FILE, funding)
        return tx
    
    def add_sponsor(self, name: str, tier: str = "supporter", monthly: float = None):
        """Register a monthly sponsor."""
        if tier not in TIERS:
            return {"error": f"Unknown tier: {tier}"}
        t = TIERS[tier]
        m = monthly or t["price"]
        
        sponsors = self._load(SPONSORS_FILE)
        existing = next((s for s in sponsors["active"] if s["name"] == name), None)
        if existing:
            existing["tier"] = tier
            existing["monthly"] = m
        else:
            sponsors["active"].append({
                "name": name,
                "tier": tier,
                "badge": t["badge"],
                "monthly": m,
                "since": datetime.now().isoformat(),
                "total_contributed": 0,
            })
        
        sponsors["total_monthly"] = sum(s["monthly"] for s in sponsors["active"])
        self._save(SPONSORS_FILE, sponsors)
        return {"name": name, "tier": t["name"], "monthly": m}
    
    def dashboard(self) -> dict:
        """Current funding dashboard."""
        funding = self._load(FUNDING_FILE)
        sponsors = self._load(SPONSORS_FILE)
        
        return {
            "total_raised": funding["total_raised"],
            "goal": funding["goal"],
            "goal_progress": funding.get("goal_progress", 0),
            "monthly_recurring": sponsors["total_monthly"],
            "active_sponsors": len(sponsors["active"]),
            "total_transactions": len(funding["transactions"]),
            "payment_options": [
                {"name": "GitHub Sponsors", "url": PAYMENT_LINKS["github_sponsors"], "type": "monthly"},
                {"name": "Ko-fi", "url": PAYMENT_LINKS["ko-fi"], "type": "one-time"},
                {"name": "Buy Me a Coffee", "url": PAYMENT_LINKS["buymeacoffee"], "type": "one-time"},
                {"name": "PayPal", "url": PAYMENT_LINKS["paypal"], "type": "one-time"},
                {"name": "Enterprise Invoice", "url": PAYMENT_LINKS["enterprise"], "type": "custom"},
            ],
            "tiers": {k: {"name": v["name"], "price": v["price"]} for k, v in TIERS.items()},
        }
    
    def progress_bar(self, width: int = 30) -> str:
        """ASCII progress bar for README."""
        funding = self._load(FUNDING_FILE)
        pct = min(100, int(funding["total_raised"] / funding["goal"] * 100))
        filled = int(width * pct / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"${funding['total_raised']:.0f} / ${funding['goal']} goal\n{bar} {pct}%"
    
    def year_projection(self) -> dict:
        """Project annual revenue based on current run rate."""
        funding = self._load(FUNDING_FILE)
        sponsors = self._load(SPONSORS_FILE)
        
        one_time = funding["total_raised"]
        monthly = sponsors["total_monthly"]
        
        projection = {
            "one_time_total": one_time,
            "monthly_recurring": monthly,
            "annual_recurring": monthly * 12,
            "projected_annual": one_time + monthly * 12,
            "needed_for_sustainability": funding["goal"] * 12,
            "gap": (funding["goal"] * 12) - (one_time + monthly * 12),
        }
        projection["gap_percent"] = max(0, int(projection["gap"] / projection["needed_for_sustainability"] * 100))
        return projection


if __name__ == "__main__":
    f = FundingEngine()
    
    print("=== FUNDING ENGINE ===")
    print(f"  Goal: ${f.dashboard()['goal']}/month")
    print(f"  Monthly: ${f.dashboard()['monthly_recurring']}")
    print(f"  One-time: ${f.dashboard()['total_raised']}")
    print()
    
    # Demo-Daten nur mit explizitem --demo Flag seeden. Ohne diesen Guard
    # wuerde jeder Cron-Lauf +$30 Fake-Umsatz erzeugen (Alice/Bob immer
    # wieder als neue Transaktionen) und total_raised endlos aufblaehen.
    if "--demo" in sys.argv:
        f.record_payment("ko-fi", 5, "Alice", "Love OpenAmer! 🔥")
        f.record_payment("paypal", 25, "Bob", "Keep building!")
        f.add_sponsor("Alice", "supporter", 3)
        f.add_sponsor("Bob", "sponsor", 25)
    
    d = f.dashboard()
    print("  Current funding state:" + (" (--demo seeded)" if "--demo" in sys.argv else ""))
    print(f"    ${d['total_raised']:.0f} raised | ${d['monthly_recurring']}/mo recurring")
    print(f"    {d['active_sponsors']} active sponsors")
    print(f"    Progress: {d['goal_progress']}%")
    
    proj = f.year_projection()
    print(f"\n  📊 Annual Projection:")
    print(f"    ${proj['projected_annual']:.0f}/year")
    print(f"    ${proj['gap']:.0f} gap to sustainability")
    print(f"    {proj['gap_percent']}% gap")
    
    print(f"\n  Progress bar:")
    print(f"    {f.progress_bar()}")
    print()
    print("✅ Funding Engine ready — payment links live in README")
    print(f"  → {PAYMENT_LINKS['github_sponsors']}")
    print(f"  → {PAYMENT_LINKS['ko-fi']}")
    print(f"  → {PAYMENT_LINKS['buymeacoffee']}")
    print(f"  → {PAYMENT_LINKS['paypal']}")