# RVC-WebUI Troubleshooting

## Issue: "Inferencing voice" Dropdown is Empty

### Problem
The RVC-WebUI API returns `None` for voice conversion because no models are loaded in the inference dropdown.

### API Investigation
```bash
curl http://localhost:7865/info
```

Shows:
```json
{
  "/infer_refresh": {
    "returns": [
      {
        "label": "Inferencing voice:",
        "description": "Option from: []"  // <-- EMPTY!
      }
    ]
  }
}
```

### Current Model Location
```
C:\Users\CRIMS\Documents\Github\Retrieval-based-Voice-Conversion-WebUI\logs\GOTHMOMMY\
├── GOTHMOMMY.pth
└── added_GOTHMOMMY_v2.index
```

### Solution Steps

#### Option 1: Load Model Through Web UI
1. Open [http://localhost:7865](http://localhost:7865) in browser
2. Go to "Model" or "Inference" tab
3. Look for model selection dropdown
4. Select/Load GOTHMOMMY model
5. Verify it appears in the dropdown

#### Option 2: Check Expected Model Location
RVC-WebUI might expect models in:
- `weights/` folder instead of `logs/`
- Specific file naming convention
- Additional config files

**Action:** Check RVC-WebUI documentation or inspect the web UI to see where it expects model files.

#### Option 3: Use Different RVC Implementation
The link you shared ([https://github.com/RVC-Project/Retrieval-based-Voice-Conversion](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion)) might have better API support.

**Comparison:**
- **Current:** `Retrieval-based-Voice-Conversion-WebUI` (fork with Gradio web interface)
- **Alternative:** `RVC-Project/Retrieval-based-Voice-Conversion` (official project)

## Next Steps

### Immediate Actions
1. **Check web UI** - Open http://localhost:7865 and look for model loading interface
2. **Check logs** - Look at RVC-WebUI console output for errors
3. **Verify model format** - Ensure .pth file is compatible with this RVC version

### Alternative: Try Official RVC Project
If RVC-WebUI continues to have issues, we can:
1. Clone the official RVC repo
2. Use their inference script directly (likely `infer.py` or similar)
3. Wrap it in our own simple API/service

### Code Changes Needed
Once model is loaded in RVC-WebUI:
- No code changes needed - our Gradio client should work
- The conversion will return actual audio instead of None

## Error Details

### What's Happening
1. Bot calls `client.predict(api_name="/infer_convert")`
2. RVC-WebUI processes request but has no model loaded
3. Returns `(info_message, None)` tuple
4. Gradio Client tries to serialize None as a file → Error
5. Our fallback copies input to output (no actual conversion)

### The Fix
Load the GOTHMOMMY model in RVC-WebUI so the dropdown shows:
```
"Option from: ['GOTHMOMMY']"
```

Then conversion will work properly.
