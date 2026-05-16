# Deployment Guide for Render

This guide explains how to deploy the Fashion Image Analyzer API to Render.

## Prerequisites

- Render account (create at https://render.com)
- GitHub or GitLab repository with this code
- Git installed locally

## Step 1: Prepare Your Repository

Ensure these files are in your repository root:

- `Procfile` - Specifies how to run the application
- `runtime.txt` - Specifies Python version
- `requirements.txt` - All Python dependencies
- `app/` - Application code

## Step 2: Deploy to Render

### Option A: Using render.yaml (Recommended)

1. Commit the `render.yaml` file to your repository
2. Go to https://dashboard.render.com
3. Click "New +" and select "Web Service"
4. Connect your GitHub/GitLab repository
5. Select the repository containing this code
6. Authorize Render to access your repository
7. Click "Deploy"

Render will automatically detect `render.yaml` and configure the service.

### Option B: Manual Configuration

1. Go to https://dashboard.render.com
2. Click "New +" and select "Web Service"
3. Connect your repository
4. Configure as follows:
   - **Name**: `fashion-image-analyzer`
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Python version**: `3.11.9`
   - **Plan**: Free (or higher based on your needs)

## Step 3: Set Environment Variables (if needed)

In the Render dashboard, navigate to your service's "Environment" settings.

Add any custom environment variables:

- `MAX_FILES_PER_REQUEST` - Maximum images per request (default: 20)
- `MAX_FILE_SIZE_MB` - Max file size in MB (default: 10)
- `REMBG_MODEL_NAME` - Background removal model (default: u2net_cloth_seg)
- `CLIP_MODEL_NAME` - CLIP model (default: openai/clip-vit-base-patch32)

## Step 4: Wait for Deployment

The deployment process will:

1. Build the Docker image
2. Install Python dependencies from `requirements.txt`
3. Start the Uvicorn server

This typically takes 3-5 minutes for the first deployment.

## Step 5: Test Your Deployment

Once deployed, your API will be available at:

```
https://fashion-image-analyzer.onrender.com
```

### Test the health endpoint:

```bash
curl https://fashion-image-analyzer.onrender.com/health
```

Expected response:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "clip_fallback_enabled": true,
  "deepfashion2_checkpoint_configured": false
}
```

### Test the root endpoint:

```bash
curl https://fashion-image-analyzer.onrender.com/
```

### Access the API documentation:

```
https://fashion-image-analyzer.onrender.com/docs
```

## Step 6: Test with Flutter App

1. Update the base URL in the Flutter app to your Render URL:

   ```dart
   _baseUrlController.text = 'https://fashion-image-analyzer.onrender.com';
   ```

2. Run the Flutter app:

   ```bash
   flutter run
   ```

3. Use the app to:
   - Check health status
   - Pick images
   - Upload and analyze images

## Troubleshooting

### Build fails with "module not found"

- Ensure all dependencies are in `requirements.txt`
- Check `Procfile` syntax

### Application crashes at startup

- Check logs in Render dashboard (Logs tab)
- Verify Python version compatibility
- Ensure `app/main.py` has no import errors

### Memory or timeout issues

- Consider upgrading from Free to Standard plan
- Optimize image sizes before upload
- Reduce `max_files_per_request` in settings

### CORS errors from Flutter app

- Add CORS middleware to `app/main.py` if needed:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Performance Notes

The free tier on Render has limitations:

- Spins down after 15 minutes of inactivity
- Limited CPU and memory
- No guaranteed performance

For production use, upgrade to the Standard or higher plan.

## Monitoring

Monitor your deployment via Render dashboard:

- View logs in real-time
- Check CPU and memory usage
- Monitor deployment health

## Updating Your Application

To update your application:

1. Make changes locally
2. Commit and push to GitHub/GitLab
3. Render automatically redeploys

To manually trigger a redeploy:

1. Go to your service in Render dashboard
2. Click "Manual Deploy" → "Deploy latest commit"

---

For more information, visit: https://render.com/docs
