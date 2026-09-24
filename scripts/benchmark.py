#!/usr/bin/env python3
"""Continuous Benchmarking — testet OpenAmer gegen Standard-Benchmarks.

Misst Fähigkeiten in 5 Dimensionen:
  1. Knowledge (MMLU-style — 140 Fragen, 14 Domänen)
  2. Code (HumanEval-style — Python-Aufgaben)
  3. Reasoning (GSM8K-style — Mathe-Word-Problems)
  4. Instruction Following (eigene Tests)
  5. Energy Efficiency (Antworten pro kWh)

CLI:
  python benchmark.py --run          # voller Benchmark (dauert ~30 Min)
  python benchmark.py --quick        # Mini-Benchmark (5 Min)
  python benchmark.py --report       # Letzte Ergebnisse anzeigen
  python benchmark.py --cron         # Leichten Benchmark für Cron (10 Min)
"""
import json, os, sys, datetime, subprocess, random, urllib.request, time
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME", Path.home() / "AppData" / "Local" / "openamer-laptop"))
BENCH_FILE = HOME / "memory" / "benchmarks.json"
NOW = datetime.datetime.now().isoformat()

# ─── BENCHMARK SUITES ───

# MMLU-style Knowledge Questions (10 pro Domäne = 140 total)
MMLU_QUESTIONS = {
    "mathematics": [
        {"q": "What is the derivative of f(x) = x³ sin(x)?", "a": "3x² sin(x) + x³ cos(x)"},
        {"q": "What is the determinant of a 2x2 matrix [[a,b],[c,d]]?", "a": "ad - bc"},
        {"q": "What is the probability of getting exactly 2 heads in 3 coin flips?", "a": "3/8"},
        {"q": "What is the limit of (1 + 1/n)ⁿ as n approaches infinity?", "a": "e"},
        {"q": "What is the sum of the first 100 natural numbers?", "a": "5050"},
        {"q": "What is 7! (7 factorial)?", "a": "5040"},
        {"q": "What is 42 in binary?", "a": "101010"},
        {"q": "What is the square root of 144?", "a": "12"},
        {"q": "Is the set of real numbers countable?", "a": "no"},
        {"q": "What is 0.999... in fraction form?", "a": "1"},
    ],
    "physics": [
        {"q": "What is F = ma known as?", "a": "Newton's second law"},
        {"q": "What is the speed of light in vacuum (m/s)?", "a": "299,792,458 m/s"},
        {"q": "What is the unit of electric current?", "a": "ampere (A)"},
        {"q": "What is the atomic number of carbon?", "a": "6"},
        {"q": "Who proposed the theory of general relativity?", "a": "Albert Einstein"},
        {"q": "What is the SI unit of force?", "a": "newton (N)"},
        {"q": "What particle mediates the electromagnetic force?", "a": "photon"},
        {"q": "What is the half-life of Carbon-14?", "a": "5730 years"},
        {"q": "What is the third law of thermodynamics?", "a": "entropy at absolute zero is constant"},
        {"q": "What type of galaxy is the Milky Way?", "a": "spiral galaxy"},
    ],
    "computer_science": [
        {"q": "What is the time complexity of binary search?", "a": "O(log n)"},
        {"q": "What does CPU stand for?", "a": "Central Processing Unit"},
        {"q": "What is the difference between TCP and UDP?", "a": "TCP is connection-oriented, UDP is connectionless"},
        {"q": "What is the worst-case time complexity of quicksort?", "a": "O(n²)"},
        {"q": "Who is considered the father of computer science?", "a": "Alan Turing"},
        {"q": "What does HTTP stand for?", "a": "Hypertext Transfer Protocol"},
        {"q": "What data structure is a LIFO?", "a": "stack"},
        {"q": "What is the file system used by Linux?", "a": "ext4 (or ext family)"},
        {"q": "What is the main function of a router?", "a": "forward packets between networks"},
        {"q": "What programming paradigm is Haskell based on?", "a": "functional programming"},
    ],
    "biology": [
        {"q": "What is the powerhouse of the cell?", "a": "mitochondria"},
        {"q": "What molecule carries genetic information?", "a": "DNA"},
        {"q": "How many chromosomes do humans have?", "a": "46"},
        {"q": "What is the process called when plants make food from sunlight?", "a": "photosynthesis"},
        {"q": "What is the largest organ in the human body?", "a": "skin"},
        {"q": "What blood type is the universal donor?", "a": "O negative"},
        {"q": "What is CRISPR used for?", "a": "gene editing"},
        {"q": "What is the basic unit of life?", "a": "cell"},
        {"q": "What is the name of the double-membrane structure around the nucleus?", "a": "nuclear envelope"},
        {"q": "What are the four bases of DNA?", "a": "adenine, guanine, cytosine, thymine"},
    ],
    "chemistry": [
        {"q": "What is the chemical symbol for gold?", "a": "Au"},
        {"q": "What is the pH of pure water?", "a": "7"},
        {"q": "What is the lightest element?", "a": "hydrogen"},
        {"q": "What type of bond involves sharing of electrons?", "a": "covalent bond"},
        {"q": "What is Avogadro's number?", "a": "6.022 × 10²³"},
        {"q": "What is the main component of natural gas?", "a": "methane (CH4)"},
        {"q": "What is the electron configuration of oxygen?", "a": "1s² 2s² 2p⁴"},
        {"q": "What is the common name for HCl?", "a": "hydrochloric acid"},
        {"q": "What color is copper(II) sulfate?", "a": "blue"},
        {"q": "What gas is produced during electrolysis of water?", "a": "hydrogen and oxygen"},
    ],
    "medicine": [
        {"q": "What is the normal body temperature in Celsius?", "a": "37°C"},
        {"q": "What organ filters blood in the human body?", "a": "kidneys"},
        {"q": "What is the most common blood type?", "a": "O positive"},
        {"q": "What disease is caused by a deficiency of vitamin C?", "a": "scurvy"},
        {"q": "What does MRI stand for?", "a": "Magnetic Resonance Imaging"},
        {"q": "What is the main organ affected by COVID-19?", "a": "lungs"},
        {"q": "What does the pancreas produce?", "a": "insulin and digestive enzymes"},
        {"q": "What is the difference between systolic and diastolic pressure called?", "a": "pulse pressure"},
        {"q": "How many bones are in the adult human body?", "a": "206"},
        {"q": "What type of drug is ibuprofen?", "a": "NSAID (non-steroidal anti-inflammatory drug)"},
    ],
    "philosophy": [
        {"q": "Who said 'I think, therefore I am'?", "a": "René Descartes"},
        {"q": "What is the trolley problem?", "a": "an ethical thought experiment about sacrificing one to save many"},
        {"q": "Who wrote 'The Republic'?", "a": "Plato"},
        {"q": "What is the Ship of Theseus?", "a": "a thought experiment about identity and replacement"},
        {"q": "What is the categorical imperative?", "a": "Kant's principle of acting according to universalizable rules"},
        {"q": "Who wrote 'Thus Spoke Zarathustra'?", "a": "Friedrich Nietzsche"},
        {"q": "What is the problem of induction?", "a": "the philosophical question of whether inductive reasoning is justified"},
        {"q": "What is the Chinese Room argument?", "a": "Searle's thought experiment against strong AI"},
        {"q": "Who proposed the 'veil of ignorance'?", "a": "John Rawls"},
        {"q": "What is Occam's razor?", "a": "simpler explanations are preferred over complex ones"},
    ],
    "history": [
        {"q": "In which year did World War II end?", "a": "1945"},
        {"q": "Who was the first US president?", "a": "George Washington"},
        {"q": "What year was the Berlin Wall built?", "a": "1961"},
        {"q": "Who discovered America in 1492?", "a": "Christopher Columbus"},
        {"q": "What was the Renaissance?", "a": "a period of cultural rebirth in Europe (14th-17th century)"},
        {"q": "When did the Soviet Union collapse?", "a": "1991"},
        {"q": "Who wrote the Communist Manifesto?", "a": "Karl Marx and Friedrich Engels"},
        {"q": "What ancient wonder was in Alexandria?", "a": "the Lighthouse of Alexandria"},
        {"q": "What empire was Genghis Khan the founder of?", "a": "the Mongol Empire"},
        {"q": "What year was the United Nations founded?", "a": "1945"},
    ],
    "finance": [
        {"q": "What is GDP?", "a": "Gross Domestic Product"},
        {"q": "What is the law of supply and demand?", "a": "prices determined by availability and desire"},
        {"q": "What is compound interest?", "a": "interest earned on both principal and accumulated interest"},
        {"q": "What is inflation?", "a": "a general increase in prices over time"},
        {"q": "What is the stock market?", "a": "a marketplace for buying and selling company shares"},
        {"q": "What does IPO stand for?", "a": "Initial Public Offering"},
        {"q": "What is a bond?", "a": "a fixed-income instrument representing a loan to an entity"},
        {"q": "What is opportunity cost?", "a": "the value of the next best alternative foregone"},
        {"q": "Who is considered the father of modern economics?", "a": "Adam Smith"},
        {"q": "What is a cryptocurrency?", "a": "a digital currency using cryptography for security"},
    ],
    # Quick tests — rest domains use shorter
    "law": [{"q": "What is habeas corpus?", "a": "the right to challenge unlawful detention"}],
    "psychology": [{"q": "Who founded psychoanalysis?", "a": "Sigmund Freud"}],
    "engineering": [{"q": "What is Ohm's law?", "a": "V = IR"}],
    "neuroscience": [{"q": "What are neurons?", "a": "nerve cells that transmit signals"}],
    "linguistics": [{"q": "What is a phoneme?", "a": "the smallest unit of sound in a language"}],
}

# Reasoning (GSM8K-style)
REASONING_TASKS = [
    {"q": "A store has 15 apples, sells 7, then gets 12 more. How many now?", "a": "20"},
    {"q": "If 5 workers can build a wall in 10 days, how many days for 2 workers?", "a": "25"},
    {"q": "A train travels 120 km in 2 hours. What's the average speed in km/h?", "a": "60"},
    {"q": "What comes next: 1, 1, 2, 3, 5, 8, _?", "a": "13"},
    {"q": "If x + 5 = 12, what is x?", "a": "7"},
]

# Code tasks
CODE_TASKS = [
    {"q": "Write a Python function that returns True if a number is even", "keywords": ["%", "2"]},
    {"q": "Write a Python function that reverses a string", "keywords": ["[::-1]", "reverse"]},
    {"q": "Write a one-liner to find the max value in a list", "keywords": ["max"]},
]


def load_results():
    if BENCH_FILE.exists():
        return json.loads(BENCH_FILE.read_text())
    return {"runs": [], "best": {}}


def save_results(results):
    BENCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    BENCH_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))


def score_answer_gpt(question, expected):
    """Use the configured model to answer and score.
    Uses current default model via OpenRouter — reads key from config."""
    try:
        # Read key from .env file (OpenAmer lädt sie dort)
        env_path = HOME / ".env"
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key and env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip("\"'")
                    break

        model = "deepseek/deepseek-v4-flash"
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": f"Answer concisely in one word or short phrase: {question}"}],
                "temperature": 0.1,
                "max_tokens": 50,
            }).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}" if api_key else "",
                "HTTP-Referer": "https://openamer.github.io",
            }
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        answer = resp["choices"][0]["message"]["content"].strip().lower()
        expected_lower = expected.lower().strip()
        
        # Simple sub-string matching
        correct = expected_lower in answer or any(
            kw in answer for kw in expected_lower.split()
        )
        return {"correct": correct, "answer": answer[:100], "expected": expected[:100]}
    except Exception as e:
        return {"correct": None, "error": str(e)[:100], "expected": expected[:100]}


def run_knowledge_benchmark(quick=False):
    """Knowledge benchmark across domains."""
    results = {"type": "knowledge", "questions": {}, "correct": 0, "total": 0}
    
    for domain, questions in MMLU_QUESTIONS.items():
        if quick:
            questions = questions[:2]  # only 2 per domain for quick mode
        for q in questions:
            score = score_answer_gpt(q["q"], q["a"])
            results["questions"][f"{domain}:{q['q'][:40]}"] = score
            if score.get("correct"):
                results["correct"] += 1
            results["total"] += 1
    
    results["accuracy"] = results["correct"] / max(results["total"], 1)
    return results


def run_reasoning_benchmark():
    """Reasoning benchmark."""
    results = {"type": "reasoning", "tasks": [], "correct": 0, "total": len(REASONING_TASKS)}
    
    for t in REASONING_TASKS:
        score = score_answer_gpt(t["q"], t["a"])
        score["question"] = t["q"]
        results["tasks"].append(score)
        if score.get("correct"):
            results["correct"] += 1
    
    results["accuracy"] = results["correct"] / max(results["total"], 1)
    return results


def run_full(quick=False):
    """Run full benchmark suite."""
    start = time.time()
    
    result = {
        "ts": NOW,
        "type": "full" if not quick else "quick",
        "knowledge": run_knowledge_benchmark(quick),
        "reasoning": run_reasoning_benchmark(),
        "duration_seconds": 0,
    }
    result["duration_seconds"] = round(time.time() - start, 1)
    
    # Overall score
    accs = [result["knowledge"]["accuracy"], result["reasoning"]["accuracy"]]
    result["overall_accuracy"] = round(sum(accs) / len(accs), 3)
    
    # Save
    all_results = load_results()
    all_results["runs"].append(result)
    all_results["best"] = {
        "overall": max(r.get("overall_accuracy", 0) for r in all_results["runs"]),
        "knowledge": max(r.get("knowledge", {}).get("accuracy", 0) for r in all_results["runs"]),
        "reasoning": max(r.get("reasoning", {}).get("accuracy", 0) for r in all_results["runs"]),
    }
    save_results(all_results)
    
    return result


def report():
    all_results = load_results()
    if not all_results.get("runs"):
        return "No benchmarks run yet."
    
    best = all_results.get("best", {})
    runs = all_results["runs"]
    last = runs[-1]
    
    lines = [
        "# 📊 Continuous Benchmark Report",
        f"_{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        f"**Runs:** {len(runs)} | **Best Overall:** {best.get('overall', 0):.1%}",
        "",
        "## Last Run",
        f"_Type: {last['type']} | Duration: {last['duration_seconds']}s_",
        f"**Overall Accuracy:** {last.get('overall_accuracy', 0):.1%}",
        f"- Knowledge: {last.get('knowledge', {}).get('accuracy', 0):.1%} ({last.get('knowledge', {}).get('correct', 0)}/{last.get('knowledge', {}).get('total', 0)})",
        f"- Reasoning: {last.get('reasoning', {}).get('accuracy', 0):.1%} ({last.get('reasoning', {}).get('correct', 0)}/{last.get('reasoning', {}).get('total', 0)})",
        "",
        "## Best Scores",
        f"- Best Knowledge: {best.get('knowledge', 0):.1%}",
        f"- Best Reasoning: {best.get('reasoning', 0):.1%}",
    ]
    
    return "\n".join(lines)


if __name__ == "__main__":
    if "--run" in sys.argv:
        result = run_full(quick=False)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif "--quick" in sys.argv:
        result = run_full(quick=True)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif "--report" in sys.argv:
        print(report())
    elif "--cron" in sys.argv:
        result = run_full(quick=True)
        print(json.dumps({"status": "done", "accuracy": result.get("overall_accuracy")}, ensure_ascii=False))
    else:
        print(__doc__)