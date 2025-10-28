# How to Load GOTHMOMMY Model in RVC-WebUI

## Current Status
✅ RMVPE pitch extraction model installed: `assets/rmvpe/`
❌ GOTHMOMMY voice model not loaded in inference dropdown

## Your Model Files Location
```
C:\Users\CRIMS\Documents\Github\Retrieval-based-Voice-Conversion-WebUI\logs\GOTHMOMMY\
├── GOTHMOMMY.pth           (voice model weights)
└── added_GOTHMOMMY_v2.index    (voice features index)
```

## How to Load Model in RVC-WebUI

### Step 1: Check if Model is in Correct Location
RVC-WebUI typically expects models in one of these locations:
- `weights/` folder (for trained models)
- `logs/{model_name}/` folder (your current location)

Your model **is** in the right place (`logs/GOTHMOMMY/`).

### Step 2: Load Model Through Web UI

1. **Open RVC-WebUI:** http://localhost:7865

2. **Look for the "Model" tab** or "Inference" section

3. **Find the "Inferencing voice" dropdown**
   - It's currently showing as empty
   - There should be a "Refresh" button nearby

4. **Click the Refresh button** (🔄) next to the dropdown
   - This should scan the `logs/` and `weights/` folders
   - Should populate the dropdown with available models

5. **Select "GOTHMOMMY"** from the dropdown

6. **Verify the index file is auto-selected**
   - Should show: `logs/GOTHMOMMY/added_GOTHMOMMY_v2.index`

### Step 3: Test Conversion Through Web UI

Before using the bot:
1. Upload a test audio file (or use the one already there)
2. Click "Convert" button
3. Verify you get output audio with the voice converted
4. Check for any error messages

### Common Issues

#### If Model Still Doesn't Appear:
1. **Wrong file format:** Model should be `.pth` file
2. **Incomplete model:** Need both `.pth` and `.index` files
3. **Wrong folder structure:** Should be `logs/GOTHMOMMY/*.pth` not `logs/*.pth`

#### If Conversion Fails:
1. **RMVPE not found:** Check `assets/rmvpe/` has model files
2. **GPU issues:** RVC might need GPU, check console for errors
3. **Audio format:** Input should be `.wav` file

## Expected Result

Once model is loaded, the API should show:
```json
{
  "Inferencing voice": {
    "Option from": ["GOTHMOMMY"]  // ✅ Model appears!
  }
}
```

Then our bot will automatically work!

## Alternative: Copy Model to Weights Folder

If refresh doesn't work, try:
```bash
# Create weights folder if it doesn't exist
mkdir C:\Users\CRIMS\Documents\Github\Retrieval-based-Voice-Conversion-WebUI\weights

# Copy model files
copy "C:\Users\CRIMS\Documents\Github\Retrieval-based-Voice-Conversion-WebUI\logs\GOTHMOMMY\GOTHMOMMY.pth" "C:\Users\CRIMS\Documents\Github\Retrieval-based-Voice-Conversion-WebUI\weights\GOTHMOMMY.pth"
```

Then refresh the web UI.
