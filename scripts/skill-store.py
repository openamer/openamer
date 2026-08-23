"""OpenAmer Skill-Store — 70/30 Split, Registry, Payments

API-Endpunkte für:
  - Skills registrieren (Creator)
  - Skills kaufen (User)
  - Auszahlungen (70% an Creator)
  - Bewertungen
  - Discoverability

Läuft als API-Server oder via Plugin-System.
"""
import json, os, time, uuid, hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

STORE_DIR = Path(os.path.expanduser("~")) / "AppData" / "Local" / "openamer-laptop" / "store"
SKILLS_REGISTRY = STORE_DIR / "registry.json"
TRANSACTIONS = STORE_DIR / "transactions.json"
CREATORS = STORE_DIR / "creators.json"

TIERS = {
    "free": {"min_price": 0, "max_price": 0, "split": 0.70},
    "basic": {"min_price": 5, "max_price": 15, "split": 0.70},
    "pro": {"min_price": 20, "max_price": 50, "split": 0.70},
    "enterprise": {"min_price": 100, "max_price": 500, "split": 0.70},
}

@dataclass
class StoreSkill:
    id: str
    name: str
    version: str
    author: str
    description: str
    tier: str
    price: float
    category: str
    tags: list[str]
    created: str
    downloads: int
    rating: float
    verified: bool

@dataclass
class Creator:
    id: str
    username: str
    email: str
    joined: str
    skills_count: int
    total_earned: float
    balance: float

@dataclass
class Transaction:
    id: str
    skill_id: str
    buyer: str
    amount: float
    creator_share: float
    platform_share: float
    timestamp: str
    status: str


class SkillStore:
    def __init__(self):
        os.makedirs(STORE_DIR, exist_ok=True)
        self._ensure_file(SKILLS_REGISTRY, [])
        self._ensure_file(TRANSACTIONS, [])
        self._ensure_file(CREATORS, [])
    
    def _ensure_file(self, path, default):
        if not path.exists():
            path.write_text(json.dumps(default, indent=2))
    
    def _load(self, path):
        return json.loads(path.read_text())
    
    def _save(self, path, data):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    def register_skill(self, name: str, author: str, description: str, 
                       tier: str = "basic", price: float = None, 
                       category: str = "general", tags: list[str] = None) -> dict:
        """Register a new skill in the store."""
        if tier not in TIERS:
            return {"error": f"Invalid tier: {tier}. Choose: {list(TIERS.keys())}"}
        
        tier_config = TIERS[tier]
        if price is None:
            price = tier_config["min_price"]
        if price < tier_config["min_price"] or price > tier_config["max_price"]:
            return {"error": f"Price {price} outside {tier} range: {tier_config['min_price']}-{tier_config['max_price']}"}
        
        skill = StoreSkill(
            id=str(uuid.uuid4())[:8],
            name=name,
            version="1.0.0",
            author=author,
            description=description,
            tier=tier,
            price=price,
            category=category,
            tags=tags or [],
            created=datetime.now().isoformat(),
            downloads=0,
            rating=0.0,
            verified=False,
        )
        
        registry = self._load(SKILLS_REGISTRY)
        registry.append(asdict(skill))
        self._save(SKILLS_REGISTRY, registry)
        
        # Track creator
        self._track_creator(author)
        
        return {
            "id": skill.id,
            "name": skill.name,
            "price": skill.price,
            "creator_share": skill.price * 0.70,
            "platform_share": skill.price * 0.30,
            "message": f"Registered! 70% ({skill.price * 0.70:.2f}) goes to you on each sale."
        }
    
    def _track_creator(self, username: str):
        creators = self._load(CREATORS)
        existing = next((c for c in creators if c["username"] == username), None)
        if existing:
            existing["skills_count"] += 1
        else:
            creators.append(asdict(Creator(
                id=str(uuid.uuid4())[:8],
                username=username,
                email=f"{username}@openamer.store",
                joined=datetime.now().isoformat(),
                skills_count=1,
                total_earned=0.0,
                balance=0.0,
            )))
        self._save(CREATORS, creators)
    
    def buy_skill(self, skill_id: str, buyer: str) -> dict:
        """Purchase a skill. Returns payment info."""
        registry = self._load(SKILLS_REGISTRY)
        skill = next((s for s in registry if s["id"] == skill_id), None)
        if not skill:
            return {"error": f"Skill {skill_id} not found"}
        
        creator_share = skill["price"] * 0.70
        platform_share = skill["price"] * 0.30
        
        tx = Transaction(
            id=str(uuid.uuid4())[:12],
            skill_id=skill_id,
            buyer=buyer,
            amount=skill["price"],
            creator_share=creator_share,
            platform_share=platform_share,
            timestamp=datetime.now().isoformat(),
            status="completed",
        )
        
        transactions = self._load(TRANSACTIONS)
        transactions.append(asdict(tx))
        self._save(TRANSACTIONS, transactions)
        
        # Update download count + creator balance
        skill["downloads"] += 1
        self._save(SKILLS_REGISTRY, registry)
        
        creators = self._load(CREATORS)
        creator = next((c for c in creators if c["username"] == skill["author"]), None)
        if creator:
            creator["total_earned"] += creator_share
            creator["balance"] += creator_share
        self._save(CREATORS, creators)
        
        return {
            "tx_id": tx.id,
            "skill": skill["name"],
            "amount": skill["price"],
            "creator_earned": creator_share,
            "platform_earned": platform_share,
            "status": "completed",
            "message": f"Purchase complete. {creator_share:.2f} goes to @{skill['author']}."
        }
    
    def list_skills(self, category: str = None, tier: str = None, search: str = None) -> list[dict]:
        """Browse the skill store."""
        registry = self._load(SKILLS_REGISTRY)
        results = registry
        
        if category:
            results = [s for s in results if s["category"] == category]
        if tier:
            results = [s for s in results if s["tier"] == tier]
        if search:
            results = [s for s in results if search.lower() in s["name"].lower() or 
                      search.lower() in s["description"].lower()]
        
        return sorted(results, key=lambda s: s["downloads"], reverse=True)
    
    def creator_dashboard(self, username: str) -> dict:
        """Creator earnings dashboard."""
        creators = self._load(CREATORS)
        creator = next((c for c in creators if c["username"] == username), None)
        if not creator:
            return {"error": f"Creator @{username} not found"}
        
        registry = self._load(SKILLS_REGISTRY)
        skills = [s for s in registry if s["author"] == username]
        
        transactions = self._load(TRANSACTIONS)
        skill_ids = [s["id"] for s in skills]
        earnings = [t for t in transactions if t["skill_id"] in skill_ids]
        
        return {
            "username": username,
            "skills": len(skills),
            "total_earned": creator["total_earned"],
            "balance": creator["balance"],
            "recent_transactions": earnings[-10:],
            "payout_available": creator["balance"] >= 20,
        }
    
    def stats(self) -> dict:
        """Store statistics."""
        registry = self._load(SKILLS_REGISTRY)
        transactions = self._load(TRANSACTIONS)
        creators = self._load(CREATORS)
        
        total_earned = sum(c["total_earned"] for c in creators)
        total_platform = sum(t["platform_share"] for t in transactions)
        
        return {
            "total_skills": len(registry),
            "total_creators": len(creators),
            "total_sales": len(transactions),
            "total_creator_earnings": total_earned,
            "total_platform_revenue": total_platform,
            "categories": list(set(s["category"] for s in registry)),
            "tiers": {t: len([s for s in registry if s["tier"] == t]) for t in TIERS},
        }


store = SkillStore()


if __name__ == "__main__":
    # Demo
    print("=== OPENAMER SKILL-STORE DEMO ===")
    
    r1 = store.register_skill("Slack-to-Notion Sync", "damir", 
        "Sync Slack messages to Notion databases automatically", 
        tier="basic", price=15, category="productivity")
    print(f"  Registered: {r1['name']} — ${r1['price']} (70% = ${r1['creator_share']})")
    
    r2 = store.register_skill("GitHub Issue Auto-Triage", "community-user",
        "AI-powered issue categorization and assignment",
        tier="pro", price=35, category="devops")
    print(f"  Registered: {r2['name']} — ${r2['price']}")
    
    r3 = store.register_skill("Daily Standup Reporter", "damir",
        "Auto-generates daily standup reports from git activity",
        tier="free", price=0, category="productivity")
    print(f"  Registered: {r3['name']} (FREE)")
    
    # Demo purchase
    buy = store.buy_skill(r1["id"], "customer@company.com")
    print(f"  Purchase: ${buy['amount']} — Creator earns ${buy['creator_earned']}")
    
    # Stats
    stats = store.stats()
    print(f"  Store: {stats['total_skills']} skills, {stats['total_creators']} creators")
    print(f"  Revenue: ${stats['total_platform_revenue']:.2f} platform / ${stats['total_creator_earnings']:.2f} creators")
    
    # Dashboard
    dash = store.creator_dashboard("damir")
    print(f"  @damir: {dash['skills']} skills, ${dash['total_earned']} earned")
    
    print("\n✅ Skill-Store operational (70/30 split)")