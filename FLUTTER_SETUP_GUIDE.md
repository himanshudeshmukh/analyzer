# Flutter Test App Setup Guide

This directory contains a complete Flutter application for testing the Fashion Image Analyzer API.

## Quick Start

### 1. Create Flutter Project Structure

```bash
flutter create fashion_image_analyzer_app
cd fashion_image_analyzer_app
```

### 2. Update pubspec.yaml

Replace the contents of `pubspec.yaml` with the provided `pubspec.yaml` file in this repository.

### 3. Replace Main App Code

Replace `lib/main.dart` with the provided `flutter_test_app.dart`:

```bash
cp ../flutter_test_app.dart lib/main.dart
```

### 4. Get Dependencies

```bash
flutter pub get
```

## Features

The test app includes:

- ✅ **Health Check** - Verify API is running
- ✅ **Image Picker** - Select clothing images from device
- ✅ **Batch Upload** - Send multiple images at once
- ✅ **Real-time Status** - See processing status
- ✅ **Result Display** - View analysis results
- ✅ **Error Handling** - Connection and timeout handling

## Testing Scenarios

### Scenario 1: Local Testing

1. Start your FastAPI server locally:

   ```bash
   cd /path/to/analyzer
   python -m uvicorn app.main:app --reload
   ```

2. In the Flutter app, set base URL to:

   ```
   http://localhost:8000
   ```

3. Test endpoints:
   - Click "Check Health" to verify connection
   - Pick images and click "Analyze"

### Scenario 2: Remote Testing (Render Deployment)

1. Deploy to Render using instructions in `DEPLOYMENT_GUIDE.md`

2. Once deployed, update the base URL to:

   ```
   https://fashion-image-analyzer.onrender.com
   ```

3. Click "Check Health" to verify deployment
4. Test with clothing images

## Test Images

For testing, use clear clothing images:

- Well-lit product photos
- Single garments preferred for initial testing
- Supported formats: JPG, PNG
- Recommended size: 1-5 MB per image

## API Endpoints Being Tested

| Endpoint             | Method | Purpose                 |
| -------------------- | ------ | ----------------------- |
| `/`                  | GET    | Get API info            |
| `/health`            | GET    | Check service health    |
| `/v1/analyze-images` | POST   | Analyze clothing images |

## Troubleshooting Flutter App

### App won't connect to localhost

- **Windows**: Use your machine IP instead of `localhost`
  ```
  http://192.168.x.x:8000
  ```
- Ensure firewall allows traffic on port 8000
- Check API is running with `curl http://localhost:8000/health`

### Images not uploading

- Check image size (max 10 MB)
- Verify network connectivity
- Check server logs for errors

### Timeout errors

- Increase timeout in code (currently 2 minutes)
- Check server CPU/memory usage
- Reduce number of images per batch

### CORS errors

- Add CORS middleware to FastAPI app
- See `DEPLOYMENT_GUIDE.md` for code example

## Platform-Specific Setup

### Android

1. Add permissions to `android/app/src/main/AndroidManifest.xml`:

   ```xml
   <uses-permission android:name="android.permission.INTERNET" />
   <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
   ```

2. Update `android/app/build.gradle`:
   ```gradle
   android {
       compileSdkVersion 34
   }
   ```

### iOS

1. Update `ios/Podfile`:

   ```ruby
   platform :ios, '12.0'
   ```

2. Request permissions in `ios/Runner/Info.plist`:
   ```xml
   <key>NSPhotoLibraryUsageDescription</key>
   <string>This app needs photo library access to test image analysis</string>
   ```

## Building for Production

### Android APK

```bash
flutter build apk --release
# Output: build/app/outputs/flutter-apk/app-release.apk
```

### iOS App

```bash
flutter build ios --release
# Follow Xcode instructions for App Store submission
```

## API Response Format

Expected analysis response:

```json
{
  "request_id": "unique-id",
  "status": "success",
  "processed_count": 1,
  "error_count": 0,
  "results": [
    {
      "filename": "image.jpg",
      "image_id": "uuid",
      "status": "success",
      "garment": {
        "garment_group": "top",
        "category": {
          "label": "shirt",
          "confidence": 0.95,
          "alternatives": []
        },
        "color_family": {
          "label": "black",
          "confidence": 0.88
        },
        "dominant_hex_colors": ["#000000", "#333333"]
      },
      "processed_image_path": "/artifacts/processed/uuid.png"
    }
  ]
}
```

## Performance Tips

1. **Batch Processing**: Upload 2-5 images at once for efficiency
2. **Image Optimization**: Resize large images before upload
3. **Caching**: App caches health status for better UX
4. **Timeouts**: Server may need 30-60 seconds for first request (model loading)

## Development Mode

For Flutter development with hot reload:

```bash
flutter run -v
```

## Contact & Support

For API documentation, visit: `https://your-deploy-url/docs`

The Swagger UI provides interactive API testing and detailed documentation.
