import 'dart:async';
import 'dart:convert';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../core/theme.dart';
import '../models/analysis.dart';
import '../providers/active_session_provider.dart';
import '../providers/providers.dart';

/// Live camera preview. A native [CameraPreview] runs on-device; throttled
/// frames are streamed to the backend over WebSocket, which returns the crop
/// detection box drawn as an overlay (the API analogue of the WebRTC preview).
/// "Capture & analyse" sends one frame through the same /analyze pipeline.
class CameraScreen extends ConsumerStatefulWidget {
  const CameraScreen({super.key});

  @override
  ConsumerState<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends ConsumerState<CameraScreen> {
  CameraController? _controller;
  WebSocketChannel? _ws;
  Timer? _ticker;
  bool _sending = false;
  bool _initializing = true;
  String? _error;
  CameraDetection? _detection;

  @override
  void initState() {
    super.initState();
    _setup();
  }

  Future<void> _setup() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        setState(() {
          _error = 'No camera found on this device.';
          _initializing = false;
        });
        return;
      }
      final controller = CameraController(
        cameras.first,
        ResolutionPreset.medium,
        enableAudio: false,
      );
      await controller.initialize();
      if (!mounted) return;

      final id = ref.read(activeSessionProvider).id!;
      final ws = WebSocketChannel.connect(
          Uri.parse(ref.read(apiClientProvider).cameraWsUrl(id)));
      ws.stream.listen(
        (data) {
          try {
            final map = jsonDecode(data as String) as Map<String, dynamic>;
            if (mounted) setState(() => _detection = CameraDetection.fromJson(map));
          } catch (_) {}
        },
        onError: (_) {},
        onDone: () {},
      );

      setState(() {
        _controller = controller;
        _ws = ws;
        _initializing = false;
      });

      // Throttle: push ~2 frames/sec to the backend for detection.
      _ticker = Timer.periodic(const Duration(milliseconds: 500), (_) => _pushFrame());
    } catch (e) {
      setState(() {
        _error = 'Could not start the camera: $e';
        _initializing = false;
      });
    }
  }

  Future<void> _pushFrame() async {
    final controller = _controller;
    final ws = _ws;
    if (controller == null || ws == null || _sending) return;
    if (!controller.value.isInitialized || controller.value.isTakingPicture) return;
    _sending = true;
    try {
      final shot = await controller.takePicture();
      final bytes = await shot.readAsBytes();
      ws.sink.add(bytes);
    } catch (_) {
      // Drop this frame; the next tick retries.
    } finally {
      _sending = false;
    }
  }

  Future<void> _capture() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;
    final shot = await controller.takePicture();
    final bytes = await shot.readAsBytes();
    _teardown();
    ref.read(appModeProvider.notifier).state = AppMode.chat;
    await ref.read(activeSessionProvider.notifier).analyze(bytes, shot.name);
  }

  void _teardown() {
    _ticker?.cancel();
    _ws?.sink.close();
    _controller?.dispose();
    _ticker = null;
    _ws = null;
    _controller = null;
  }

  @override
  void dispose() {
    _teardown();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_initializing) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return _ErrorState(message: _error!);
    }
    final controller = _controller!;
    final detection = _detection;

    return Column(
      children: [
        Expanded(
          child: Container(
            color: Colors.black,
            child: Center(
              child: AspectRatio(
                aspectRatio: controller.value.aspectRatio,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    CameraPreview(controller),
                    if (detection != null)
                      CustomPaint(painter: _BoxPainter(detection)),
                    Positioned(
                      left: 0,
                      right: 0,
                      bottom: 0,
                      child: Container(
                        padding: const EdgeInsets.all(10),
                        color: Colors.black54,
                        child: Text(
                          detection?.box != null
                              ? '${detection!.label}  ${(detection.confidence * 100).toStringAsFixed(0)}%'
                              : (detection?.label ?? 'Connecting…'),
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: FilledButton.icon(
            onPressed: _capture,
            icon: const Icon(Icons.camera_alt_outlined),
            label: const Text('Capture & analyse'),
            style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(52)),
          ),
        ),
      ],
    );
  }
}

class _BoxPainter extends CustomPainter {
  final CameraDetection det;
  _BoxPainter(this.det);

  @override
  void paint(Canvas canvas, Size size) {
    final box = det.box;
    if (box == null || det.width == 0 || det.height == 0) return;
    final sx = size.width / det.width;
    final sy = size.height / det.height;
    final rect = Rect.fromLTRB(
        box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy);
    final paint = Paint()
      ..color = AppTheme.corn
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;
    canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(8)), paint);
  }

  @override
  bool shouldRepaint(covariant _BoxPainter old) => old.det != det;
}

class _ErrorState extends ConsumerWidget {
  final String message;
  const _ErrorState({required this.message});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.videocam_off_outlined, size: 48),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.tonal(
              onPressed: () =>
                  ref.read(appModeProvider.notifier).state = AppMode.upload,
              child: const Text('Upload a photo instead'),
            ),
          ],
        ),
      ),
    );
  }
}
