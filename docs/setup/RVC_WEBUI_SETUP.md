# RVC-WebUI Setup Guide

This guide will help you set up RVC-WebUI as an API server for voice conversion.

## Step 1: Download RVC-WebUI

### Option A: Quick Install (Recommended)
Download the pre-packaged version with all dependencies:
https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/releases

### Option B: Clone from GitHub
```bash
git clone https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI.git
cd Retrieval-based-Voice-Conversion-WebUI
```

## Step 2: Install Dependencies

RVC-WebUI has its own Python environment. Follow their installation guide:
- For Windows: Run `download_files.bat` and then `install.bat`
- For Linux/Mac: Follow the instructions in their README

## Step 3: Add Your Voice Models

1. Place your GOTHMOMMY model folder in RVC-WebUI's models directory:
   ```
   RVC-WebUI/
   └── logs/
       └── GOTHMOMMY/
           ├── GOTHMOMMY.pth
           └── added_GOTHMOMMY_v2.index
   ```

2. Or use the WebUI to upload models through the interface

## Step 4: Start RVC-WebUI in API Mode

### Using the WebUI:
1. Run the start script (e.g., `go-web.bat` on Windows)
2. Open browser to http://localhost:7865
3. Go to "Inference" tab
4. You can also enable API mode in settings

### Using Command Line (API Mode):
```bash
python infer-web.py --api --listen 0.0.0.0 --port 7865
```

## Step 5: Test the API

Once RVC-WebUI is running, test it:

```bash
curl http://localhost:7865/api
```

You should see API documentation or confirmation it's running.

## Step 6: Configure Your Bot

Update your `.env` file:

```bash
# RVC Configuration
RVC_ENABLED=true
RVC_MODE=webui  # Use "webui" instead of "inferpy"
RVC_WEBUI_URL=http://localhost:7865
DEFAULT_RVC_MODEL=GOTHMOMMY
```

## API Endpoints

RVC-WebUI typically provides these API endpoints:

### Convert Audio
```
POST http://localhost:7865/api/infer
Content-Type: multipart/form-data

Parameters:
- audio_file: WAV/MP3 file to convert
- model_name: Name of voice model (e.g., "GOTHMOMMY")
- pitch: Pitch shift in semitones (default: 0)
- index_rate: Feature retrieval ratio 0.0-1.0 (default: 0.75)
- filter_radius: Smoothing (default: 3)
- f0_method: "crepe", "harvest", "pm", "dio"
```

### List Models
```
GET http://localhost:7865/api/models
```

## Troubleshooting

### Port Already in Use
Change the port in your `.env`:
```bash
RVC_WEBUI_URL=http://localhost:7866
```

And start RVC-WebUI with:
```bash
python infer-web.py --api --port 7866
```

### Models Not Found
- Make sure models are in the `logs/` directory
- Refresh the models list in the WebUI
- Check model file names match your config

### Connection Refused
- Make sure RVC-WebUI is running
- Check firewall settings
- Verify the URL in your `.env` file

## Next Steps

Once RVC-WebUI is running:

1. **Test the setup:**
   ```bash
   .venv311\Scripts\python.exe test_rvc_webui.py
   ```

2. **Start your bot:**
   ```bash
   .venv311\Scripts\python.exe main.py
   ```

3. **Use voice commands in Discord:**
   - `/join` - Join voice channel
   - `/speak Hello world` - TTS + RVC conversion
   - `/speak_as GOTHMOMMY Hello` - Use specific model

## Benefits of RVC-WebUI

- ✅ Stable and actively maintained
- ✅ Includes all required models (rmvpe, hubert)
- ✅ Web interface for managing models
- ✅ Better error handling
- ✅ Supports multiple models simultaneously
- ✅ Training capabilities if you want custom voices

## Resources

- RVC-WebUI GitHub: https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI
- Documentation: Check the `docs/` folder in the repo
- Discord: Join their community for help
