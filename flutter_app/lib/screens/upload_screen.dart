import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../providers/active_session_provider.dart';
import '../providers/providers.dart';

class UploadScreen extends ConsumerStatefulWidget {
  const UploadScreen({super.key});

  @override
  ConsumerState<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends ConsumerState<UploadScreen> {
  Uint8List? _bytes;
  String _filename = 'upload.jpg';
  final _note = TextEditingController();

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _pick() async {
    final picker = ImagePicker();
    final file = await picker.pickImage(source: ImageSource.gallery, imageQuality: 95);
    if (file == null) return;
    final bytes = await file.readAsBytes();
    setState(() {
      _bytes = bytes;
      _filename = file.name;
    });
  }

  Future<void> _analyze() async {
    if (_bytes == null) return;
    final notifier = ref.read(activeSessionProvider.notifier);
    ref.read(appModeProvider.notifier).state = AppMode.chat;
    await notifier.analyze(_bytes!, _filename, note: _note.text.trim());
  }

  @override
  Widget build(BuildContext context) {
    final busy = ref.watch(activeSessionProvider).busy;
    final scheme = Theme.of(context).colorScheme;

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Upload a leaf photo',
            style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 16),
        GestureDetector(
          onTap: _pick,
          child: Container(
            height: 260,
            decoration: BoxDecoration(
              color: scheme.surfaceContainerHighest.withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: scheme.outlineVariant,
                style: BorderStyle.solid,
              ),
            ),
            clipBehavior: Clip.antiAlias,
            child: _bytes == null
                ? Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.add_photo_alternate_outlined,
                          size: 48, color: scheme.onSurfaceVariant),
                      const SizedBox(height: 10),
                      const Text('Tap to choose an image'),
                      Text('JPG, PNG or WEBP',
                          style: TextStyle(
                              fontSize: 12, color: scheme.onSurfaceVariant)),
                    ],
                  )
                : Image.memory(_bytes!, fit: BoxFit.cover, width: double.infinity),
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _note,
          decoration: const InputDecoration(
            labelText: 'Add a note (optional)',
            hintText: 'e.g. spots spreading fast on lower leaves',
          ),
        ),
        const SizedBox(height: 20),
        FilledButton.icon(
          onPressed: (_bytes == null || busy) ? null : _analyze,
          icon: busy
              ? const SizedBox(
                  width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.biotech_outlined),
          label: Text(busy ? 'Analysing…' : 'Analyse image'),
        ),
        if (_bytes != null)
          TextButton.icon(
            onPressed: busy ? null : _pick,
            icon: const Icon(Icons.refresh, size: 18),
            label: const Text('Choose a different image'),
          ),
      ],
    );
  }
}
