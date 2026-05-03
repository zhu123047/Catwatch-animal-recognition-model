# EPIC 3 AI API Frontend Usage

This document explains how the frontend should call the EPIC 3 image-based
species identification API.

## API Base URL

Public API base URL:

```text
http://130.162.194.202
```

Health check:

```http
GET http://130.162.194.202/health
```

Expected response:

```json
{
  "status": "ok",
  "classifier_mode": "species_finetuned",
  "database": "echoes_of_earth"
}
```

`classifier_mode: "species_finetuned"` means the trained Australian species
model is loaded and ready.

## Identify Species

Endpoint:

```http
POST http://130.162.194.202/api/epic3/identify
```

Request content type:

```text
multipart/form-data
```

Required form fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `image` | File | Yes | Animal or feather photo uploaded by the user |
| `postcode` | String | Yes | 4-digit Victorian postcode, for example `3029` |
| `top_k` | Number | No | Number of predictions to return. Recommended: `3` |

## JavaScript Example

```js
const API_BASE = "http://130.162.194.202";

export async function identifySpecies(file, postcode, topK = 3) {
  const formData = new FormData();
  formData.append("image", file);
  formData.append("postcode", postcode);
  formData.append("top_k", String(topK));

  const response = await fetch(`${API_BASE}/api/epic3/identify`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Species identification failed: ${errorText}`);
  }

  return response.json();
}
```

## Simple HTML Example

```html
<input id="species-photo" type="file" accept="image/*" />
<input id="postcode" type="text" maxlength="4" placeholder="Postcode" />
<button id="identify-button">Identify</button>

<pre id="result"></pre>

<script>
  const API_BASE = "http://130.162.194.202";

  async function identifySpecies(file, postcode) {
    const formData = new FormData();
    formData.append("image", file);
    formData.append("postcode", postcode);
    formData.append("top_k", "3");

    const response = await fetch(`${API_BASE}/api/epic3/identify`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(await response.text());
    }

    return response.json();
  }

  document.querySelector("#identify-button").addEventListener("click", async () => {
    const fileInput = document.querySelector("#species-photo");
    const postcodeInput = document.querySelector("#postcode");
    const resultBox = document.querySelector("#result");

    if (!fileInput.files.length) {
      resultBox.textContent = "Please upload an image.";
      return;
    }

    try {
      const result = await identifySpecies(fileInput.files[0], postcodeInput.value);
      resultBox.textContent = JSON.stringify(result, null, 2);
    } catch (error) {
      resultBox.textContent = error.message;
    }
  });
</script>
```

## Example Response

```json
{
  "postcode": "3029",
  "filename": "test.jpg",
  "classifier_mode": "species_finetuned",
  "predictions": [
    {
      "scientific_name": "Gymnorhina tibicen",
      "common_name": "Australian Magpie",
      "confidence": 0.269,
      "source": "species_finetuned"
    }
  ],
  "species_insights": [
    {
      "prediction": {
        "scientific_name": "Gymnorhina tibicen",
        "common_name": "Australian Magpie",
        "confidence": 0.269,
        "source": "species_finetuned"
      },
      "conservation_status": "Not listed",
      "local_sighting_count": 16,
      "lga_sighting_count": 69,
      "victoria_sighting_count": 2105,
      "latest_local_cached_at": "2026-04-14T12:12:06.209857",
      "latest_victoria_cached_at": "2026-04-14T12:12:06.209857",
      "suburb_name": "Werribee",
      "lga_name": "Wyndham"
    }
  ],
  "warnings": []
}
```

## Recommended UI Mapping

- Main species name: `predictions[0].common_name`
- Scientific name: `predictions[0].scientific_name`
- Confidence: `predictions[0].confidence`
- Conservation status: `species_insights[0].conservation_status`
- Local postcode sightings: `species_insights[0].local_sighting_count`
- LGA sightings: `species_insights[0].lga_sighting_count`
- Victoria sightings: `species_insights[0].victoria_sighting_count`
- Suburb: `species_insights[0].suburb_name`
- LGA: `species_insights[0].lga_name`

## Current Trained Species

The current fine-tuned MVP model supports these 5 Australian species:

- Pacific Black Duck, `Anas superciliosa`
- Australian Magpie, `Gymnorhina tibicen`
- Crimson Rosella, `Platycercus elegans`
- Rainbow Lorikeet, `Trichoglossus moluccanus`
- Common Brushtail Possum, `Trichosurus vulpecula`

## Error Handling

Common HTTP errors:

- `400`: invalid postcode, empty image, or uploaded file is not an image.
- `413`: uploaded image is too large.
- `502`: API service is starting or temporarily unavailable behind Nginx.

The backend may also return a successful response with a non-empty `warnings`
array. For example, if PostgreSQL lookup is temporarily unavailable, the model
prediction can still be returned while database insight fields may be empty.

## Notes

- The frontend does not need to call PostgreSQL directly.
- The frontend does not need to know where the model file is stored.
- Browser CORS is already enabled on the backend.
- Use `http://130.162.194.202/api/epic3/identify` for public access.

