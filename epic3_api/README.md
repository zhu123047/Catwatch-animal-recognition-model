# EPIC 3 Species Identification API

This is a standalone API for EPIC 3. It accepts an uploaded image plus a
Victorian postcode, returns top-k species predictions from a local vision model,
then enriches those predictions with read-only PostgreSQL lookups from the
existing biodiversity tables.

**Code walkthrough (request path, classifier backends, training pipeline):** see [`CODE_FROM_THE_START.md`](CODE_FROM_THE_START.md).

## Safety

- The API does not manage Docker, Kubernetes, volumes, backups, or restores.
- Database code opens a read-only PostgreSQL session.
- The only SQL statements in the API are `SELECT` queries.
- No tables are created, updated, inserted into, or deleted from.
- Model files are stored outside Docker in `models/epic3/`.
- Training images are stored outside Docker in `data/epic3/`.

## Install

```bash
cd /home/ubuntu/zwx/FIT5120
python3 -m venv .venv-epic3
source .venv-epic3/bin/activate
pip install -r requirements-epic3.txt
```

`torch` and `torchvision` are included because the real image classifier uses
EfficientNet. On first ImageNet fallback run, torchvision may download the
pretrained weights into the current user's torch cache.

## Run

Set database connection variables if your local values differ from the defaults:

```bash
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=echoes_of_earth
export PGUSER=postgres
export PGPASSWORD='P@ssw0rd'
export EPIC3_CLASSIFIER_BACKEND=auto

uvicorn epic3_api.main:app --reload --host 127.0.0.1 --port 8003
```

Classifier backend options:

- `auto`: use `models/epic3/species_classifier.pt` if present, otherwise use
  ImageNet fallback, then demo as last resort.
- `species_finetuned`: require the local Australian species model.
- `imagenet`: require torchvision ImageNet fallback.
- `demo`: deterministic development fallback only.

## Identify an Image

```bash
curl -X POST http://127.0.0.1:8003/api/epic3/identify \
  -F postcode=3029 \
  -F top_k=3 \
  -F image=@/path/to/photo.jpg
```

## Public Access

This machine exposes the API through Nginx on port 80. FastAPI still only
listens on `127.0.0.1:8003`, so the model service is not directly exposed.

Public base URL:

```text
http://130.162.194.202
```

Frontend endpoint:

```text
POST http://130.162.194.202/api/epic3/identify
```

Health check:

```bash
curl http://130.162.194.202/health
```

Services:

```bash
sudo systemctl status epic3-api.service
sudo systemctl status nginx
```

The `epic3-open-http.service` oneshot service ensures TCP port 80 is allowed in
the local iptables firewall after reboot. If the public IP changes, update the
frontend URL accordingly.

## Train the Australian Species Model

The training pipeline follows the EPIC 3 document's open-data approach, but
keeps strict local limits so it does not disturb Docker/PostgreSQL.

Download a small iNaturalist subset:

```bash
cd /home/ubuntu/zwx/FIT5120
source .venv-epic3/bin/activate
python3 -m epic3_training.download_inaturalist_subset \
  --max-species 5 \
  --images-per-species 80 \
  --max-total-mb 2048
```

Fine-tune EfficientNet on the downloaded Australian species subset:

```bash
python3 -m epic3_training.train_species_classifier \
  --epochs 3 \
  --batch-size 8
```

Evaluate the exported model:

```bash
python3 -m epic3_training.evaluate_species_classifier
```

The model and labels are exported to:

```text
/home/ubuntu/zwx/FIT5120/models/epic3/species_classifier.pt
/home/ubuntu/zwx/FIT5120/models/epic3/labels.json
```

After those files exist, `EPIC3_CLASSIFIER_BACKEND=auto` will load the fine-tuned
Australian species model automatically.

## Tests

```bash
cd /home/ubuntu/zwx/FIT5120
python3 -m pytest tests
```

The tests mock API dependencies and do not connect to the real PostgreSQL
database.

