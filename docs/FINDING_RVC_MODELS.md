# Finding RVC Voice Models

Now that RVC is installed, you need voice models (`.pth` files) to convert voices!

## Where to Find RVC Models

### 1. **HuggingFace** (Recommended)
Search for RVC models: https://huggingface.co/models?search=rvc

Popular models:
- Character voices (anime, game characters)
- Celebrity voice models
- Singer voice models

**How to download:**
1. Find a model you like
2. Go to "Files and versions"
3. Download the `.pth` file
4. Also download the `.index` file if available
5. Place both in `./data/voice_models/`

### 2. **AI Hub**
https://aihub.wtf

Large collection of pre-trained RVC models including:
- Game characters
- Anime characters
- Real people (celebrities, streamers)

### 3. **RVC Model Collections on GitHub**
Search GitHub for "RVC models" or specific characters you want

### 4. **Train Your Own**
Use RVC-WebUI to train models on voice samples:
https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI

## For Arby n the Chief

Since these are specific Machinima characters, you'll likely need to:

### Option 1: Find Similar Voices
Look for:
- **Chief**: Deep, aggressive male voices (military, action characters)
- **Arby**: British, sophisticated male voices

### Option 2: Train Your Own
1. Download RVC-WebUI
2. Collect voice samples from Arby n the Chief episodes
3. Train models for each character (requires ~10 minutes of clean audio)
4. Export the `.pth` files

## Model File Structure

Your `./data/voice_models/` folder should look like:
```
data/
└── voice_models/
    ├── chief.pth
    ├── chief.index (optional but improves quality)
    ├── arby.pth
    └── arby.index (optional but improves quality)
```

## Quick Test Models

For testing, you can search for these popular/easy-to-find models:
- "SpongeBob RVC model"
- "Morgan Freeman RVC model"
- "Master Chief RVC model" (might exist!)

## Testing Your Models

Once you have a model, test it with:
```bash
.venv311\Scripts\python.exe test_rvc.py
```

This will:
1. List all available models
2. Pick a test audio file (from your Kokoro/Edge TTS tests)
3. Convert it using your RVC model
4. Save the output

## Next Steps

1. **Download a test model** from HuggingFace or AI Hub
2. **Place it in** `./data/voice_models/`
3. **Run the test script** to make sure everything works
4. **Then train or find** specific Arby/Chief models for your bot

## Example: Downloading from HuggingFace

```bash
# Example URL (replace with actual model you find):
# https://huggingface.co/username/model-name

# Download using git or browser:
1. Click "Files and versions"
2. Download the .pth file (usually 50-200MB)
3. Download the .index file if available
4. Move to ./data/voice_models/
```

## Pro Tip: Voice Blending

You can also blend multiple voices! Once you have models working, the RVC service supports mixing voices for unique results.
