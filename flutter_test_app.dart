// Fashion Image Analyzer - Flutter Test App
// This Flutter application tests the FastAPI backend for clothing image analysis
// Features: Health check, batch image analysis, image picker integration

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'dart:io';
import 'dart:convert';

import 'package:Kaivon/presentation/screens/tripPlanner/fashionPedia.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:image_picker/image_picker.dart';

void main() => runApp(const Main());


// ═══════════════════════════════════════════════════════════════════════════
// MAIN APP — Flutter client for the Fashionpedia FastAPI service.
//
// This app provides 3 tabs:
//   Tab 1: Health Check   → GET  /api/v1/health
//   Tab 2: Image Analysis → POST /api/v1/images/analyze
//   Tab 3: Outfit Recommend → POST /api/v1/outfits/recommend
// ═══════════════════════════════════════════════════════════════════════════



class Main extends StatelessWidget {
  const Main({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Fashion Apps',
      theme: ThemeData(
        primarySwatch: Colors.deepPurple,
        useMaterial3: true,
      ),
      home: const MainHome(),
    );
  }
}

class MainHome extends StatelessWidget {
  const MainHome({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Row(
          children: [
            TextButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const FashionAnalyzerApp(),
                ),
              ),
              child: const Text("Analyzer"),
            ),
            TextButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const FashionpediaApp(),
                ),
              ),
              child: const Text("Recommend"),
            ),
          ],
        ),
      ),
    );
  }
}

class FashionAnalyzerApp extends StatelessWidget {
  const FashionAnalyzerApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Fashion Image Analyzer',
      theme: ThemeData(
        primarySwatch: Colors.deepPurple,
        useMaterial3: true,
      ),
      home: const AnalyzerHome(),
    );
  }
}

class AnalyzerHome extends StatefulWidget {
  const AnalyzerHome({Key? key}) : super(key: key);

  @override
  State<AnalyzerHome> createState() => _AnalyzerHomeState();
}

class _AnalyzerHomeState extends State<AnalyzerHome> {
  static const String _baseUrl = 'https://fashion-image-analyzer.onrender.com';
  
  final ImagePicker _imagePicker = ImagePicker();
  final List<File> _selectedImages = [];
  
  String _statusMessage = '';
  bool _isLoading = false;
  Map<String, dynamic> _analysisResult = {};
  Map<String, dynamic> _healthStatus = {};

  // Test the health endpoint
  Future<void> _checkHealth() async {
    setState(() {
      _isLoading = true;
      _statusMessage = 'Checking health...';
    });

    try {
      final response = await http.get(
        Uri.parse('$_baseUrl/health'),
        headers: {'Accept': 'application/json'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        setState(() {
          _healthStatus = jsonDecode(response.body);
          _statusMessage = '✓ Health check passed!';
        });

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Status: ${_healthStatus['status']}'),
            backgroundColor: Colors.green,
            duration: const Duration(seconds: 2),
          ),
        );
      } else {
        setState(() {
          _statusMessage =
              'Health check failed. Status: ${response.statusCode}';
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: ${response.statusCode}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } on SocketException catch (e) {
      setState(() {
        _statusMessage = 'Connection error: ${e.message}';
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Cannot connect to server'),
          backgroundColor: Colors.red,
        ),
      );
    } catch (e) {
      setState(() {
        _statusMessage = 'Error: $e';
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  // Pick images from device
  Future<void> _pickImages() async {
    try {
      final List<XFile> images = await _imagePicker.pickMultiImage(
        imageQuality: 85,
      );

      if (images.isNotEmpty) {
        setState(() {
          _selectedImages.clear();
          _selectedImages.addAll(images.map((e) => File(e.path)));
          _statusMessage = '${_selectedImages.length} image(s) selected';
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error picking images: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  // Analyze selected images
  Future<void> _analyzeImages() async {
    if (_selectedImages.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please select at least one image'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    setState(() {
      _isLoading = true;
      _statusMessage = 'Analyzing ${_selectedImages.length} image(s)...';
      _analysisResult = {};
    });

    try {
      final uri = Uri.parse('$_baseUrl/v1/analyze-images');

      // Build multipart request
      final request = http.MultipartRequest('POST', uri);

      // Add each image file
      for (File imageFile in _selectedImages) {
        final stream = http.ByteStream(imageFile.openRead());
        final length = await imageFile.length();
        final multipartFile = http.MultipartFile(
          'files',
          stream,
          length,
          filename: imageFile.path.split('/').last,
        );
        request.files.add(multipartFile);
      }

      // Add optional parameter
      request.fields['include_base64'] = 'false';

      // Send request
      final streamedResponse = await request.send().timeout(
        const Duration(minutes: 2),
        onTimeout: () {
          throw TimeoutException('Request timeout');
        },
      );

      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final result = jsonDecode(response.body);
        setState(() {
          _analysisResult = result;
          _statusMessage = '✓ Analysis completed!';
        });

        _showAnalysisResults(result);
      } else {
        setState(() {
          _statusMessage =
              'Analysis failed. Status: ${response.statusCode}';
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: ${response.statusCode}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } on SocketException {
      setState(() {
        _statusMessage = 'Connection error';
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Cannot connect to server'),
          backgroundColor: Colors.red,
        ),
      );
    } catch (e) {
      setState(() {
        _statusMessage = 'Error: $e';
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  // Display analysis results in a dialog
  void _showAnalysisResults(Map<String, dynamic> result) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Analysis Results'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Processed ${result['processed_count'] ?? 0} image(s)',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                'Status: ${result['status'] ?? 'unknown'}',
                style: const TextStyle(fontSize: 14),
              ),
              const SizedBox(height: 8),
              if (result['error_count'] != null)
                Text(
                  'Errors: ${result['error_count']}',
                  style: const TextStyle(
                    fontSize: 14,
                    color: Colors.red,
                  ),
                ),
              const SizedBox(height: 16),
              if ((result['results'] as List?)?.isNotEmpty ?? false)
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Details:',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      jsonEncode(result['results']).substring(0, 200) + '...',
                      style: const TextStyle(
                        fontSize: 12,
                        fontFamily: 'monospace',
                      ),
                    ),
                  ],
                ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Fashion Image Analyzer'),
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Health Check Button
            ElevatedButton.icon(
              onPressed: _isLoading ? null : _checkHealth,
              icon: const Icon(Icons.health_and_safety),
              label: const Text('Check Health'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.blue,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  vertical: 12,
                  horizontal: 24,
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Status/Health Display
            if (_healthStatus.isNotEmpty)
              Card(
                elevation: 2,
                color: Colors.green.shade50,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Health Status',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text('Status: ${_healthStatus['status']}'),
                      Text('Version: ${_healthStatus['version']}'),
                      Text(
                        'CLIP Fallback: ${_healthStatus['clip_fallback_enabled'] == true ? 'Enabled' : 'Disabled'}',
                      ),
                      Text(
                        'DeepFashion2: ${_healthStatus['deepfashion2_checkpoint_configured'] == true ? 'Configured' : 'Not Configured'}',
                      ),
                    ],
                  ),
                ),
              ),

            if (_statusMessage.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: _statusMessage.contains('✓')
                        ? Colors.green.shade100
                        : Colors.orange.shade100,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: _statusMessage.contains('✓')
                          ? Colors.green
                          : Colors.orange,
                    ),
                  ),
                  child: Text(
                    _statusMessage,
                    style: TextStyle(
                      color: _statusMessage.contains('✓')
                          ? Colors.green.shade800
                          : Colors.orange.shade800,
                    ),
                  ),
                ),
              ),

            const SizedBox(height: 24),

            // Image Selection Section
            Card(
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Image Selection',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 12),
                    ElevatedButton.icon(
                      onPressed: _isLoading ? null : _pickImages,
                      icon: const Icon(Icons.image),
                      label: const Text('Pick Images'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.purple,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(
                          vertical: 12,
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    if (_selectedImages.isNotEmpty)
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${_selectedImages.length} image(s) selected:',
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(height: 8),
                          SizedBox(
                            height: 100,
                            child: ListView.builder(
                              scrollDirection: Axis.horizontal,
                              itemCount: _selectedImages.length,
                              itemBuilder: (context, index) => Padding(
                                padding: const EdgeInsets.only(right: 8),
                                child: Container(
                                  decoration: BoxDecoration(
                                    border:
                                        Border.all(color: Colors.purple),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: ClipRRect(
                                    borderRadius: BorderRadius.circular(8),
                                    child: Image.file(
                                      _selectedImages[index],
                                      fit: BoxFit.cover,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),

            // Analysis Button
            ElevatedButton.icon(
              onPressed: _isLoading || _selectedImages.isEmpty
                  ? null
                  : _analyzeImages,
              icon: _isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor:
                            AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    )
                  : const Icon(Icons.analytics),
              label: Text(
                _isLoading
                    ? 'Analyzing...'
                    : 'Analyze ${_selectedImages.isNotEmpty ? '(${_selectedImages.length})' : ''}',
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.deepOrange,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                disabledBackgroundColor: Colors.grey,
              ),
            ),

            if (_analysisResult.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: Card(
                  elevation: 2,
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Last Analysis Result',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Processed: ${_analysisResult['processed_count'] ?? 0}',
                        ),
                        Text(
                          'Status: ${_analysisResult['status'] ?? 'unknown'}',
                        ),
                        if (_analysisResult['error_count'] != null)
                          Text(
                            'Errors: ${_analysisResult['error_count']}',
                            style: const TextStyle(color: Colors.red),
                          ),
                      ],
                    ),
                  ),
                ),
              ),

            const SizedBox(height: 24),

            // API Endpoints Reference
            Card(
              elevation: 2,
              color: Colors.grey.shade100,
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'API Endpoints',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'GET / - Root endpoint\n'
                      'GET /health - Health check\n'
                      'POST /v1/analyze-images - Analyze images',
                      style: TextStyle(
                        fontSize: 12,
                        fontFamily: 'monospace',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class TimeoutException implements Exception {
  final String message;
  TimeoutException(this.message);

  @override
  String toString() => message;
}
