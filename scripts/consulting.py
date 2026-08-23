"""OpenAmer Consulting Automation — Service-Template + Preise

Ein Agent der Berater-Arbeit automatisiert:
  - Workflow-Audit
  - Pipeline-Bau
  - Enterprise-Stacks
  - Fractional CTO (24/7)

Preise: Festpreis pro Deliverable (nicht pro Stunde).
"""
import json, os, time
from pathlib import Path
from datetime import datetime

SERVICES = {
    "quick-audit": {
        "name": "Quick Audit",
        "price_eur": 499,
        "delivery_hours": 4,
        "description": "Full workflow analysis + 5 automation blueprints",
        "deliverables": [
            "Current workflow map",
            "5 automation blueprints",
            "ROI projection",
            "Implementation cost estimate",
        ],
    },
    "pipeline-build": {
        "name": "Pipeline Build",
        "price_eur": 1999,
        "delivery_hours": 48,
        "description": "Custom agent pipeline deployed + tested",
        "deliverables": [
            "End-to-end agent pipeline",
            "CI/CD integration",
            "Test suite + monitoring",
            "Deployment playbook",
        ],
    },
    "enterprise-stack": {
        "name": "Enterprise Stack",
        "price_eur": 4999,
        "delivery_hours": 120,
        "description": "Complete AI agent infrastructure",
        "deliverables": [
            "Full agent infrastructure",
            "SSO/SAML integration",
            "Compliance docs (SOC2/GDPR)",
            "SLA monitoring",
            "Team training",
        ],
    },
    "fractional-cto": {
        "name": "Fractional CTO",
        "price_eur": 9999,
        "delivery_hours": 720,
        "description": "Full-time AI agent managing DevOps, QA, monitoring, HR",
        "deliverables": [
            "24/7 agent operations",
            "Monthly KPI reports",
            "Team coordination",
            "Tech stack management",
            "Incident response",
            "Capacity planning",
        ],
        "monthly": True,
    },
}


class ConsultingAutomation:
    def __init__(self):
        self.orders_file = Path(os.path.expanduser("~")) / "AppData" / "Local" / "openamer-laptop" / "store" / "consulting.json"
        os.makedirs(self.orders_file.parent, exist_ok=True)
    
    def list_services(self):
        """Show all available consulting services."""
        return [
            {
                "id": k,
                "name": v["name"],
                "price": f"€{v['price_eur']:,}",
                "delivery": f"{v['delivery_hours']}h",
                "description": v["description"],
                "deliverables": v["deliverables"],
                "monthly": v.get("monthly", False),
            }
            for k, v in SERVICES.items()
        ]
    
    def order(self, service_id: str, company: str, contact: str, context: str = ""):
        """Order a consulting service."""
        if service_id not in SERVICES:
            return {"error": f"Unknown service: {service_id}"}
        
        service = SERVICES[service_id]
        order = {
            "id": str(int(time.time() * 1000)),
            "service": service_id,
            "company": company,
            "contact": contact,
            "context": context,
            "price": service["price_eur"],
            "ordered_at": datetime.now().isoformat(),
            "status": "pending",
            "delivery_hours": service["delivery_hours"],
        }
        
        # Save order
        orders = []
        if self.orders_file.exists():
            orders = json.loads(self.orders_file.read_text())
        orders.append(order)
        self.orders_file.write_text(json.dumps(orders, indent=2))
        
        # Trigger agent
        return {
            "order_id": order["id"],
            "service": service["name"],
            "price": f"€{service['price_eur']:,}",
            "delivery": f"{service['delivery_hours']}h",
            "status": "agent dispatched",
            "message": f"🤖 OpenAmer agent assigned to build '{service['name']}' for {company}. ETA: {service['delivery_hours']}h."
        }
    
    def status(self, order_id: str):
        """Check order status."""
        if not self.orders_file.exists():
            return {"error": "No orders"}
        orders = json.loads(self.orders_file.read_text())
        order = next((o for o in orders if o["id"] == order_id), None)
        if not order:
            return {"error": f"Order {order_id} not found"}
        return order
    
    def revenue_report(self):
        """Total consulting revenue."""
        if not self.orders_file.exists():
            return {"total": 0, "orders": 0}
        orders = json.loads(self.orders_file.read_text())
        total = sum(o["price"] for o in orders)
        return {
            "total_orders": len(orders),
            "total_revenue": f"€{total:,}",
            "by_service": {s: len([o for o in orders if o["service"] == s]) for s in SERVICES},
        }


if __name__ == "__main__":
    c = ConsultingAutomation()
    
    print("=== CONSULTING SERVICES ===")
    for s in c.list_services():
        monthly = " (monthly)" if s["monthly"] else ""
        print(f"  {s['name']:<20} {s['price']:>10}{monthly}")
        for d in s["deliverables"][:3]:
            print(f"    → {d}")
        print()
    
    print("=== DEMO ORDER ===")
    order = c.order("quick-audit", "Acme Corp", "cto@acme.com", 
                    "Need to automate our deployment pipeline")
    print(f"  Order #{order['order_id']}: {order['message']}")
    
    print("\n✅ Consulting Automation ready")