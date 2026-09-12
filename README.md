# Delhi Air Quality Digital Twin (pure Python)

Offline dual-archive RAG + hybrid execution for Delhi air quality. No website.

```
User (natural language)
    → Technical decomposition
    → Dual retrieval
         ├── Simulation equations archive
         └── Prediction equations archive
    → Synthesis (equation package + coupling)
    → Hybrid execution on 6-station series
         (prediction baseline + simulation scenario delta)
```

## Requirements

- Python 3.10+
- `numpy` only

```bash
pip install numpy
```

## Quick start

```bash
cd aq_dtwin
python main.py --list-stations
python main.py
python main.py --demo
python main.py -q "Forecast PM2.5 for 72h if stubble increases by 40%"
python main.py -q "Reduce traffic 30% at Anand Vihar" --horizon 48
python main.py -q "..." --station "Rohini" --stubble 1.4 --json
```

## Layout

```
aq_dtwin/
├── main.py                 # CLI
├── data/
│   ├── stations.csv        # 6-location snapshot (1 Jan 2025 00:00)
│   ├── observations.py     # CSV load + 7-day synthesised history
│   └── equations.py        # Simulation + prediction archives
└── core/
    ├── decomposer.py       # NL → technical description + scenario %
    ├── embeddings.py       # Hashed n-gram embedder + cosine store
    ├── synthesizer.py      # Equation package
    ├── simulator.py        # Physics/process execution
    ├── predictor.py        # Data-driven forecast execution
    ├── hybrid.py           # Baseline + scenario delta coupling
    └── pipeline.py         # Orchestration
```

## Data policy

| Layer | Source |
|-------|--------|
| Ground truth | `stations.csv` (exact 6 rows) |
| Training window | 7-day hourly series synthesised from the snapshot using Delhi winter climatology |
| Simulated fields | Generated only when simulation equations execute |

Historical raw observations are primary. Simulated DT output is complementary.

## Hybrid coupling

1. Prediction equations → baseline forecast from station history
2. Simulation equations → control run + scenario run (traffic / stubble multipliers)
3. Scenario delta = mean(sim_scenario − sim_control)
4. Hybrid = baseline + delta (optional bias correction on last 48 h)
