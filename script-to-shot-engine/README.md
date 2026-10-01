<div align="center">

# 🎬 Script-to-Shot Engine

**English | [中文](README.zh-CN.md)**

**Turn scripts into shot-by-shot video prompts, ready to feed Wan 3.0 (通义万相 3.0)**

![Version](https://img.shields.io/badge/version-4.1.1-blue)
![Model](https://img.shields.io/badge/Wan_3.0-supported-blueviolet)
![Type](https://img.shields.io/badge/Skill-black)
![Prompts](https://img.shields.io/badge/prompts-Chinese-green)

Fight choreography · Dialogue standoffs · Long-scene splitting · Global style lock · Asset continuity

**🧠 Recommended models: Kimi K3 · ChatGPT 5.6 Terra or above · Claude Opus 4.6 or above**

</div>

---

## What is this

A Skill that reads your **existing art assets** (characters / scenes / weapons / props) and your script, designs the action causal chain internally, and outputs **shot-by-shot, timestamped prompts ready for video models** — you just copy and paste.

```text
镜头五（4.8-5.8秒）：光圈 f/2.8（浅景深，背景明显虚化），景别 特写，
货柜木板特写（close-up detail）固定拍摄（static shot）；球棍"砰"地砸进木板，木屑飞溅。
```

Prompts are generated in Chinese by design — Wan 3.0 handles them best that way. Every aperture value carries a Chinese depth-of-field note, every shot carries a **shot size** (never a focal length), and cinematography terms are bilingual: Chinese first, English in parentheses on first use in each unit.

## 🎯 Two scene modes

| | Action mode | Standoff mode |
|---|---|---|
| **For** | Fights, chases, gunfights, fantasy, boss battles | Negotiation, interrogation, showdowns — dialogue-driven scenes |
| **Causal chain** | Attack → Block → Hit → Impact → Recover | Pressure → Endure → Slip/Counter → New balance |
| **Shot density** | ≥10 shots per 15s, 1–2s each | 5–8 shots per 15s, 2–4s each |
| **Dialogue** | Incidental | Full script lines embedded in shots; one line per shot by default, audio-bridged across shots when the picture must leave the speaker |

Mixed scenes (talk first, fight later) can **switch modes clip by clip**.

## 📦 Output structure

```markdown
## Asset Reference Card      ← @asset names + short anchors; inferred looks auto-flagged
## Global Style Lock         ← six-slot style lock, emitted once for the whole film
## Dialogue Coverage Ledger  ← one row per script line: full original string + landing shot + status
## Video Generation Prompts  ← per clip: spatial setup → shots (seamless timestamps) → end state → constraints
## Pre-flight Notes          ← up to three honest warnings
```

- ⏱ **Closed-loop timestamps**: every shot carries start–end seconds, aperture `f/2.8` with a depth-of-field note, and a **shot size** — no focal length (`CAM-01`: writing both a size word and a mm value makes the model relax to the looser one)
- 🔗 **Long-scene splitting**: split at completed action/turning points; characters, weapons, seats, blood states carry across clips
- 🎭 **Special stylization**: flashbacks, CCTV, hallucinations can be layered onto marked segments without polluting the global lock
- 🧷 **Asset continuity**: weapon hand, downed bodies, extinguished light sources — tracked across clips

## 🧪 Rules and gate (new in v3.0.0)

Every rule is registered in [`references/rule-tiers.md`](references/rule-tiers.md) at one of four levels, each bound to a judge:

| Level | Judge | Can block delivery |
|---|---|---|
| `structural_invariant` | **script** | ✅ |
| `reviewed_invariant` | reviewer, citing evidence | needs evidence |
| `craft_default` | creator — a stated reason overrides | ❌ |
| `taste_option` | creator | ❌ never alone |

Deterministic checks are **scripts, not prose**:

```bash
python scripts/check_units.py     --delivery delivery.md      # duration math · clipping · unit format
python scripts/check_dialogue.py --script script.md --delivery delivery.md --ledger ledger.md
python scripts/check_cast.py      --delivery delivery.md      # on-screen cast · anchors · same-person declaration
```

[`evaluations/gate.py`](evaluations/gate.py) replays the fixtures in `evaluations/cases/` and fails if a guard stops biting or starts false-positiving. [`evaluations/selfcheck.py`](evaluations/selfcheck.py) audits the skill against itself. **Script red = do not deliver.**

> `FMT-01` **format guard**: a delivery that is neither the `单元 N` format nor the legacy `### Clip NN` format makes the checkers **error out instead of silently passing**. Lesson: the old timeline checker once read zero shots from a real delivery and waved through a prompt missing 6 seconds — **"couldn't read it" must never look like "it's fine"**.

Why: prose checklists cannot distinguish "I checked" from "I actually checked". A dropped half-line looks identical to a complete one.

## 🚀 Install

Drop the folder into your skills directory; new sessions pick it up automatically:

```bash
# Kimi Desktop
git clone https://github.com/jiayushi1-ux/script-to-shot-engine.git \
  "<daimon-share>/daimon/skills/script-to-shot-engine"

# Generic
git clone https://github.com/jiayushi1-ux/script-to-shot-engine.git \
  ~/.config/agents/skills/script-to-shot-engine
```

Or download the ZIP and extract it into your skills directory. Then just say **"use script-to-shot-engine on this script"**.

## 🗂 Structure

```
├── SKILL.md              # Entry: rule tiers · routing · output protocol · 3-layer gate
├── references/           # On-demand rules; rule-tiers.md registers every rule's level
├── scripts/              # Deterministic validators (dialogue coverage, timestamps)
├── evaluations/          # gate.py + cases/ — regression baseline ("no regression")
├── examples/             # Full examples (15s / 30s / 90s, action & standoff)
└── .agents/notes/        # Decision notes (implemented / rejected / simplification)
```

---

<div align="center">
Current version <b>v4.1.1</b> · Wan 3.0 only — one renderer, one set of rules
</div>
