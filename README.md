# Regula Face Matching for Maid Verification

A comprehensive face matching system using Regula's Face Web API to verify maid identity by comparing passport photos with selfies.

## 🚀 Overview

This system processes face images using Regula's Face Web API, matching passport photos with selfie images to verify identity. It's specifically designed for the "maids in folders" workflow with robust error handling and Google Sheets integration.

## 📋 Features

* **Regula Face API Integration**: Advanced face matching with confidence scores
* **Smart Image Selection**: Automatic passport vs selfie detection based on filename hints
* **Batch Processing**: Process multiple maids in parallel with progress tracking
* **Crop Extraction**: Optional face crop saving for QA and debugging
* **Google Sheets Upload**: Automated results upload with similarity scores
* **Robust Error Handling**: Graceful failure handling and detailed logging

## 🏗️ Repository Structure

```
regula_face_matching/
├── .env.example              # Environment configuration template
├── requirements.txt          # Python dependencies
├── main.py                  # Main processing script
├── src/
│   ├── adapters/
│   │   └── face_client.py   # Regula Face API client
│   └── utils/
│       └── files.py         # File handling utilities
├── data/
│   └── faces/
│       ├── 10001/           # Maid ID directory
│       │   ├── passport.jpg # Passport image
│       │   └── selfie.jpg   # Selfie image
│       └── 10002/
│           ├── kenya_passport.png
│           └── face_1.jpg
└── results/                 # Processing results
    ├── face_results.csv     # Main results CSV
    └── crops/               # Face crop images (optional)
```

## 🔧 Setup

### 1. Face API Service (Docker)

Run the Regula Face API locally:

```bash
docker run --name faceapi -d \
  -p 41101:41101 \
  -v /path/to/your/regula.license:/opt/regula/regula.license:ro \
  regulaforensics/face-api:latest
```

> **Note**: Adjust the license file path (`/Users/mohamedgomaa/regula.license`) to match your actual license location.

### 2. Python Environment

```bash
# Create and activate virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy environment template
cp env.example .env

# Edit .env with your settings
nano .env
```

**Key Configuration Options:**

```ini
# Face API
FACE_API_URL=http://localhost:41101
FACE_MATCH_THRESHOLD=0.85

# Data paths
DATA_ROOT=data/faces
RESULTS_CSV=results/face_results.csv
CROPS_DIR=results/crops

# Features
SAVE_CROPS=true

# Google Sheets (optional)
GOOGLE_SHEET_ID=your_sheet_id_here
GOOGLE_CREDENTIALS_PATH=credentials.json
```

## 📂 Data Organization

### Input Structure

Each maid should have their own directory under `data/faces/`:

```
data/faces/
├── <MAID_ID>/
│   ├── passport.jpg     # Passport photo
│   └── selfie.jpg       # Selfie photo
└── <MAID_ID>/
    ├── document.png     # Alternative naming
    └── face_photo.jpg   # Alternative naming
```

### Image Detection Logic

The system automatically detects image types using filename hints:

**Passport Keywords:** `pass`, `passport`, `doc`, `mrz`, `bio`, `id`
**Selfie Keywords:** `selfie`, `face`, `live`, `photo`, `portrait`

**Fallback Strategy:**
1. If no keywords match → use file size (passport typically larger)
2. If only one image → skip maid (needs both images)

## 🏃‍♂️ Usage

### Basic Processing

```bash
python main.py
```

### Upload Results to Google Sheets

```bash
# Manual upload (uses default CSV path from .env)
python -m src.utils.sheets_uploader

# Or specify custom CSV file
python -m src.utils.sheets_uploader path/to/custom.csv
```

### Advanced Usage

```python
from src.adapters.face_client import match_passport_and_selfie
from src.utils.files import list_image_files, choose_passport_and_selfie
from pathlib import Path

# Process specific maid
maid_dir = Path("data/faces/10001")
images = list_image_files(maid_dir)
passport, selfie = choose_passport_and_selfie(images)

if passport and selfie:
    result = match_passport_and_selfie(
        passport.read_bytes(),
        selfie.read_bytes(),
        threshold=0.85,
        save_crops=True
    )
    print(f"Similarity: {result.similarity:.3f}")
    print(f"Match: {result.decision}")
```

## 📊 Output Format

### CSV Results

```csv
inputs.maid_id,inputs.passport_path,inputs.selfie_path,outputs.similarity,outputs.match,outputs.reason,status
10001,data/faces/10001/passport.jpg,data/faces/10001/selfie.jpg,0.913,True,ok,ok
10002,data/faces/10002/kenya_passport.png,data/faces/10002/face_1.jpg,0.712,False,below threshold 0.85,ok
```

### Column Descriptions

* **inputs.maid_id**: Unique maid identifier
* **inputs.passport_path**: Path to passport image used
* **inputs.selfie_path**: Path to selfie image used
* **outputs.similarity**: Face similarity score (0.0-1.0)
* **outputs.match**: Boolean match result based on threshold
* **outputs.reason**: Match decision reason
* **status**: Processing status (`ok`, `error:...`, `skipped:...`)

### Face Crops (Optional)

When `SAVE_CROPS=true`, aligned face crops are saved to:

```
results/crops/
├── <MAID_ID>/
│   ├── passport_crop.jpg
│   └── selfie_crop.jpg
```

## 🎯 Face Matching Thresholds

### Recommended Thresholds

* **0.9+**: Very high confidence match
* **0.8-0.89**: High confidence match (recommended default: 0.85)
* **0.7-0.79**: Moderate confidence (requires manual review)
* **Below 0.7**: Low confidence (likely different people)

### Threshold Configuration

Set `FACE_MATCH_THRESHOLD` in `.env` to adjust sensitivity:

```ini
# Conservative (fewer false positives)
FACE_MATCH_THRESHOLD=0.9

# Balanced (recommended)
FACE_MATCH_THRESHOLD=0.85

# Liberal (fewer false negatives)
FACE_MATCH_THRESHOLD=0.75
```

## 🔍 Google Sheets Integration

### Setup

1. Create a Google Cloud Project
2. Enable Google Sheets and Drive APIs
3. Create credentials (OAuth 2.0) and download as `credentials.json`
4. Set `GOOGLE_SHEET_ID` in `.env`

### Upload Results

```bash
# Upload latest results
python tools/upload_sheet.py
```

The uploader will:
- Clear existing sheet data
- Upload new results with headers
- Freeze the header row
- Handle authentication automatically

## 🚦 Error Handling

### Common Issues

**Docker API not running:**
```bash
# Check if container is running
docker ps | grep faceapi

# Restart if needed
docker restart faceapi
```

**License file issues:**
```bash
# Verify license mount
docker inspect faceapi | grep -A 5 Mounts
```

**Import errors:**
```bash
# Try legacy import if new package fails
pip install regula.facesdk.webclient
```

### Status Codes

* **ok**: Successfully processed
* **skipped:not_enough_images**: Less than 2 images found
* **skipped:cant_choose_pair**: Unable to identify passport/selfie pair
* **error:...**: Processing error with details

## 🔧 Development

### Adding New Features

1. **Custom Image Selection Logic**: Modify `src/utils/files.py`
2. **Additional Face Analysis**: Extend `src/adapters/face_client.py`
3. **New Output Formats**: Update `main.py` results handling

### Testing

```bash
# Create test data
mkdir -p data/faces/test_maid
# Add test images...

# Run on single maid
python -c "
from main import run
import os
os.environ['DATA_ROOT'] = 'data/faces/test_maid'
run()
"
```

## 📈 Performance

### Optimization Features

* **Batch Processing**: Process multiple maids efficiently
* **Error Recovery**: Continue processing despite individual failures
* **Progress Tracking**: Real-time progress with tqdm
* **Optional Crops**: Skip crop generation for faster processing

### Typical Processing Times

* **Single face match**: ~1-3 seconds
* **Batch of 100 maids**: ~3-8 minutes
* **Google Sheets upload**: ~10-30 seconds

## 🔒 Security & Privacy

* Face crop images contain sensitive biometric data
* Results CSV contains similarity scores and file paths
* Google Sheets integration requires appropriate access controls
* Consider encrypting sensitive outputs in production

## 📚 References

* [Regula Face SDK Web API Documentation](https://docs.regulaforensics.com/face-sdk-web-service/)
* [Python Client GitHub Repository](https://github.com/regulaforensics/FaceSDK-web-python-client)
* [Face API Docker Image](https://hub.docker.com/r/regulaforensics/face-api)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project follows the same licensing as the Regula Face SDK. Ensure you have appropriate licenses for production use.
