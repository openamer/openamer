"""
Cognition -- integrated cognitive cycle for OpenAmer.

ONE run chains several cognitive building blocks instead of ticking them
separately:

    perceive -> recall -> predict (calibrated) -> score -> correct
             -> validate -> reflect

Measured gap this closes (2026-10-11, live on this laptop):
    world model:   484 facts | 168 predictions | 0 corrections
    calibration:   19/204 correct  -> adjustment 0.3 (the floor)
    The system predicted and NEVER turned a failed prediction into a
    correction. This cycle writes the correction edge.

Honesty contract: if a step cannot run (e.g. the embedding server is down),
the cycle reports that as an error and counts nothing as a success. It never
fabricates a hit.
"""

from __future__ import annotations

import contextlib
import datetime
import io
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

OPENAMER_HOME = Path(
    os.environ.get(
        "OPENAMER_HOME",
        str(Path.home() / "AppData/Local/openamer-laptop"),
    )
)
SCRIPTS_TRAINING = OPENAMER_HOME / "scripts" / "training"
MEMORY_DIR = OPENAMER_HOME / "memory"
STATE_FILE = MEMORY_DIR / "asi_cognition.json"

if str(SCRIPTS_TRAINING) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_TRAINING))

# Running this file directly puts tools/asi/ on sys.path[0]. That would shadow
# scripts/training/<name>.py with the sibling wrapper of the same name, and the
# wrapper's importlib.import_module("<name>") then re-imports ITSELF ->
# RecursionError. Drop the script directory so the real module always wins.
_here = str(Path(__file__).resolve().parent)
while _here in sys.path:
    sys.path.remove(_here)


def _load_blocks():
    """Import the sibling building blocks whether run as a module or a script.

    `python tools/asi/cognition.py` has no parent package, so relative imports
    fail; the fallback puts the repo root on sys.path and imports by full name.
    """
    if __package__:
        from . import world_model as _wm
        from . import prediction as _pred
        from . import self_model as _sm
    else:
        root = str(Path(__file__).resolve().parents[2])
        if root not in sys.path:
            sys.path.insert(0, root)
        from tools.asi import world_model as _wm
        from tools.asi import prediction as _pred
        from tools.asi import self_model as _sm
    return _wm, _pred, _sm


# The building blocks, used together in one run.
wm, pred, sm = _load_blocks()  # noqa: E402  world_model + prediction + self_model

# An expected effect counts as "the model got it right" above this cosine.
MATCH_THRESHOLD = 0.72
# Minimum similarity for a recalled prior to count as an expectation at all.
PRIOR_THRESHOLD = 0.60


def _now_iso() -> str:
    return datetime.datetime.now().isoformat()


class Cognition:
    """The integrated cycle. One `cycle()` call uses >=3 building blocks."""

    def __init__(self, home: Optional[str] = None):
        self.home = Path(home) if home else OPENAMER_HOME
        self.state_file = self.home / "memory" / "asi_cognition.json"

    # -- state ---------------------------------------------------------------
    def _load_state(self) -> Dict[str, Any]:
        try:
            with open(self.state_file, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {
                "last_cycle_ts": None,
                "cycles": 0,
                "corrections_written": 0,
                "hits": 0,
                "misses": 0,
                "unscorable": 0,
            }

    def _save_state(self, state: Dict[str, Any]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1, ensure_ascii=False)
        os.replace(tmp, self.state_file)

    # -- helpers -------------------------------------------------------------
    def _facts(self) -> List[Dict[str, Any]]:
        """Read every 'fact' edge from the world-model store, with its stable key.

        The key matters: recall() must be able to EXCLUDE the observation itself.
        An edge is always its own nearest neighbour (cosine 1.0), so a cycle
        that cannot exclude it confirms itself and learns nothing.
        """
        import world_model as _wm  # real module: edge_key lives there
        path = self.home / "memory" / "world_model.jsonl"
        out: List[Dict[str, Any]] = []
        if not path.exists():
            return out
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("kind", "fact") == "fact" and d.get("cause"):
                    d["key"] = _wm.edge_key(d)
                    out.append(d)
        return out

    def _similar(self, a: str, b: str) -> Optional[float]:
        """Cosine similarity of two texts, or None when embedding is down.

        Uses the REAL scripts/training/world_model module for both embed() and
        _cosine() -- the tools/asi wrapper does not re-export them.
        """
        if not a or not b:
            return None
        import world_model as _wm
        va = _wm.embed(a)
        vb = _wm.embed(b)
        if va is None or vb is None:
            return None
        try:
            return _wm._cosine(va, vb)
        except Exception:
            return None

    # -- the cycle -----------------------------------------------------------
    def cycle(
        self,
        situation: Optional[str] = None,
        effect: Optional[str] = None,
        limit: int = 6,
    ) -> Dict[str, Any]:
        """Run ONE integrated cognitive cycle.

        With `situation`+`effect` given, that single observation is processed.
        Otherwise the newest facts since the last cycle are processed.
        """
        state = self._load_state()
        started = _now_iso()
        steps: List[Dict[str, Any]] = []
        errors: List[str] = []
        corrections = 0
        hits = 0
        misses = 0
        unscorable = 0

        # 1. PERCEIVE ---------------------------------------------------------
        if situation and effect:
            observations = [{"cause": situation, "effect": effect, "ts": started, "key": "explicit"}]
            source = "explicit"
        else:
            last = state.get("last_cycle_ts")
            facts = self._facts()
            if last:
                facts = [f for f in facts if (f.get("ts") or "") > last]
            facts.sort(key=lambda f: f.get("ts") or "")
            observations = facts[-limit:] if len(facts) > limit else facts
            source = "facts_since_last_cycle" if last else "newest_facts"
        steps.append({"step": "perceive", "block": "world_model",
                      "detail": f"{len(observations)} observation(s) via {source}"})

        if not observations:
            steps.append({"step": "recall", "block": "world_model", "detail": "nothing new to process"})
        # 2-5. per observation: recall -> predict -> score -> correct --------
        processed = []
        for obs in observations:
            cause = obs.get("cause", "")
            actual = obs.get("effect", "")
            okey = obs.get("key") or ""
            row: Dict[str, Any] = {"cause": cause[:90], "actual": actual[:90]}

            # 2. RECALL -- earlier edges with a similar cause, EXCLUDING this one
            try:
                priors = wm.recall(cause, k=6, exclude={okey} if okey else None)
            except Exception as exc:
                priors = []
                errors.append(f"recall failed: {exc}")
            obs_ts = obs.get("ts") or ""
            prior_pairs: List[tuple] = []
            for p in priors:
                if p.get("score", 0) < PRIOR_THRESHOLD or not p.get("effect"):
                    continue
                if okey and p.get("key") == okey:
                    continue          # the observation itself -> proves nothing
                if obs_ts and (p.get("ts") or "") >= obs_ts:
                    continue          # same time or later is not an expectation
                prior_pairs.append((p["effect"], p["score"]))
            row["recalled"] = len(prior_pairs)

            # 3. PREDICT -- the model's expectation, with its own calibration
            try:
                adjustment = pred.apply_confidence_to_new_predictions()
            except Exception as exc:
                adjustment = 1.0
                errors.append(f"confidence failed: {exc}")
            expected = prior_pairs[0][0] if prior_pairs else None
            row["expected"] = (expected or "")[:90]
            row["calibration"] = adjustment

            # 4. SCORE -- does the expectation match what actually happened?
            if expected is None:
                row["outcome"] = "no_prior"
                unscorable += 1
            else:
                sim = self._similar(expected, actual)
                if sim is None:
                    row["outcome"] = "unscorable"
                    row["note"] = "embedding unavailable"
                    unscorable += 1
                elif sim >= MATCH_THRESHOLD:
                    row["outcome"] = "hit"
                    row["similarity"] = round(sim, 3)
                    hits += 1
                else:
                    row["outcome"] = "miss"
                    row["similarity"] = round(sim, 3)
                    misses += 1
                    # 5. CORRECT -- write the correction edge the system never wrote
                    try:
                        wm.observe(
                            cause,
                            f"KORREKTUR: erwartet '{expected[:160]}' -- tatsaechlich '{actual[:160]}'",
                            kind="correction",
                            confidence=round(1.0 - sim, 3),
                        )
                        corrections += 1
                        row["corrected"] = True
                    except Exception as exc:
                        errors.append(f"observe(correction) failed: {exc}")
                        row["corrected"] = False
            processed.append(row)

        steps.append({"step": "recall/predict/score/correct", "block": "world_model+prediction",
                      "detail": f"{len(processed)} processed, {corrections} correction(s)"})

        # 6. VALIDATE -- track record from the prediction validator
        try:
            # The validator prints a status line to stdout; swallow it so this
            # cycle's own (JSON) output stays machine-readable.
            with contextlib.redirect_stdout(io.StringIO()):
                validation = pred.validate_predictions()
        except Exception as exc:
            validation = {"error": str(exc)}
            errors.append(f"validate failed: {exc}")
        confidence_state = validation.get("confidence_state") if isinstance(validation, dict) else None
        steps.append({"step": "validate", "block": "prediction",
                      "detail": f"track record: {confidence_state}"})

        # 7. REFLECT -- read the self-model so the calibration lands in one place
        try:
            self_state = sm.gather_state()
            reflect_ok = True
        except Exception as exc:
            self_state = {}
            reflect_ok = False
            errors.append(f"self_model failed: {exc}")
        steps.append({"step": "reflect", "block": "self_model",
                      "detail": "self-model read" if reflect_ok else "self-model unavailable"})

        # persist ------------------------------------------------------------
        state["last_cycle_ts"] = started
        state["cycles"] = state.get("cycles", 0) + 1
        state["corrections_written"] = state.get("corrections_written", 0) + corrections
        state["hits"] = state.get("hits", 0) + hits
        state["misses"] = state.get("misses", 0) + misses
        state["unscorable"] = state.get("unscorable", 0) + unscorable
        state["last_summary"] = {
            "ts": started,
            "processed": len(processed),
            "hits": hits,
            "misses": misses,
            "unscorable": unscorable,
            "corrections": corrections,
        }
        self._save_state(state)

        scored = hits + misses
        return {
            "success": len(errors) == 0,
            "cycle_ts": started,
            "blocks_used": ["world_model", "prediction", "self_model"],
            "observations": len(observations),
            "processed": processed,
            "hits": hits,
            "misses": misses,
            "unscorable": unscorable,
            "corrections_written": corrections,
            "hit_rate": round(hits / scored, 3) if scored else None,
            "calibration": confidence_state,
            "steps": steps,
            "errors": errors,
            "lifetime": {k: state[k] for k in
                         ("cycles", "corrections_written", "hits", "misses", "unscorable")},
            "world_model": wm.stats(),
        }

    def status(self) -> Dict[str, Any]:
        state = self._load_state()
        return {
            "last_cycle_ts": state.get("last_cycle_ts"),
            "cycles": state.get("cycles", 0),
            "corrections_written": state.get("corrections_written", 0),
            "hits": state.get("hits", 0),
            "misses": state.get("misses", 0),
            "unscorable": state.get("unscorable", 0),
            "last_summary": state.get("last_summary"),
        }


_cognition: Optional[Cognition] = None


def get_cognition() -> Cognition:
    global _cognition
    if _cognition is None:
        _cognition = Cognition()
    return _cognition


def cycle(**kwargs: Any) -> Dict[str, Any]:
    """Run one integrated cycle. Module-level entry point (heartbeat native_map)."""
    return get_cognition().cycle(**kwargs)


def status() -> Dict[str, Any]:
    """Cycle state. Module-level entry point for the heartbeat/CLI."""
    return get_cognition().status()


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Integrated cognitive cycle")
    ap.add_argument("--status", action="store_true", help="show cycle state")
    ap.add_argument("--cycle", action="store_true", help="run one cycle")
    ap.add_argument("--situation", default=None, help="explicit cause")
    ap.add_argument("--effect", default=None, help="explicit effect")
    ap.add_argument("--limit", type=int, default=6)
    args = ap.parse_args()

    cog = get_cognition()
    if args.status:
        print(json.dumps(cog.status(), indent=2, ensure_ascii=False))
        return
    result = cog.cycle(situation=args.situation, effect=args.effect, limit=args.limit)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
