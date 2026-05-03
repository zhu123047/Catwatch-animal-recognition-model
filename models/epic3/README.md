# Model outputs (not committed)

After training, this directory should contain:

- `species_classifier.pt` — EfficientNet-B0 fine-tuned weights  
- `labels.json` — class list aligned with `ImageFolder` / training export  

Train with:

```bash
cd /path/to/repo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-epic3.txt
python -m epic3_training.download_inaturalist_subset --help
python -m epic3_training.train_species_classifier --help
```

The API reads default paths under `models/epic3/` (see `epic3_api/config.py`).
