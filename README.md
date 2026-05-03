# Catwatch — Animal recognition (EPIC 3)

Fine-tuned **EfficientNet-B0** species classifier, **FastAPI** service, and **read-only PostgreSQL** enrichment for the Catwatch / FIT5120 project.

## Repository layout

| Folder | Purpose |
|--------|---------|
| **`epic3_api/`** | FastAPI app (`main.py`), classifier adapters, DB access, ML modules (`ml/`), and docs (`README.md`, `FRONTEND_USAGE.md`, `CODE_EXPLAIN.md`). |
| **`epic3_training/`** | iNaturalist download script, fine-tuning, evaluation; `species_targets.json` defines taxa. |
| **`tests/`** | `pytest` tests for the API (often run with `EPIC3_CLASSIFIER_BACKEND=demo`). |
| **`sql/queries/`** | Example SQL used with the biodiversity schema. |
| **`scripts/`** | Standalone import utilities (`import_epic4_suburb_scores.py`, `import_fauna_to_species_cache.py`) for related coursework data. |
| **`postgres/`** | Reference **Docker** files and `init/` SQL only — **no** database volume or `.env` secrets. |
| **`models/epic3/`** | Place **`species_classifier.pt`** and **`labels.json`** here after training (see `models/epic3/README.md`). A sample `labels.json` may be committed for structure; weights are not. |
| **`data/epic3/`** | Place downloaded training images under `images/` (see `data/epic3/README.md`). |

## Quick start

```bash
git clone https://github.com/zhu123047/Catwatch-animal-recognition-model.git
cd Catwatch-animal-recognition-model
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-epic3.txt
export PGHOST=localhost PGDATABASE=echoes_of_earth PGUSER=postgres PGPASSWORD=your_secret
export EPIC3_CLASSIFIER_BACKEND=auto   # or demo / imagenet / species_finetuned
uvicorn epic3_api.main:app --host 127.0.0.1 --port 8003
```

Detailed API usage: **`epic3_api/README.md`** and **`epic3_api/FRONTEND_USAGE.md`**.

## License / data

Training images are downloaded from **iNaturalist** under the filters in `download_inaturalist_subset.py` (research-grade observations, selected CC licenses). Respect iNaturalist and image licenses when redistributing data.
