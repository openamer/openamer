# GPU-Upgrade-Entscheidung (Stand 02.09.2026)

## Warum
Mini-OpenAmer-Training (CPU): 35 min pro Lauf, RAM-Guard blockiert oft.
Mit GPU: ~3-5 min, RAM-Druck weg, groessere Modelle (7B+) moeglich.

## Optionen (Preise gebraucht, eBay/Kleinanzeigen DE, Sept 2026)
| GPU | VRAM | Preis gebraucht | Was geht damit |
|---|---|---|---|
| RTX 3060 12GB | 12GB | 200-240 EUR | 7B-LoRA flott, 13B langsam, Training 5x schneller |
| RTX 4060 Ti 16GB | 16GB | 430-480 EUR | 13B-LoRA gut, shards weg |
| RTX 3090 24GB | 24GB | 600-700 EUR | 30B quantisiert, alle Traeume |

## Empfehlung
RTX 3060 12GB (200 EUR) reicht fuer den aktuellen Workflow komplett.
Einbau: PCIe x16 Slot, Netzteil pruefen (mind. 550W, 1x 8-Pin).

## Nach Einbau (Ich mache das automatisch)
1. CUDA-torch installieren, 2. finetune_cpu.py -> finetune_gpu.py,
3. Guards im auto_retrain.py auf VRAM statt RAM,
4. GGUF-Pfad wieder oeffnen (Qwen3.5-Support via neueren llama.cpp mit CUDA).
