import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme.dart';
import '../models/analysis.dart';
import '../providers/providers.dart';

/// The result card shown after an image is analysed: annotated image, crop &
/// disease metrics, confidence bars, fallbacks, and the visible class scores.
class DetectionCard extends ConsumerWidget {
  final AnalysisResult result;
  const DetectionCard({super.key, required this.result});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.read(apiClientProvider);
    final scheme = Theme.of(context).colorScheme;

    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
            child: Image.network(
              api.mediaUrl(result.annotatedUrl),
              fit: BoxFit.cover,
              width: double.infinity,
              loadingBuilder: (c, child, p) => p == null
                  ? child
                  : const SizedBox(
                      height: 200,
                      child: Center(child: CircularProgressIndicator())),
              errorBuilder: (c, e, s) => Container(
                height: 160,
                color: scheme.surfaceContainerHighest,
                child: const Center(child: Icon(Icons.broken_image_outlined)),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (result.inconclusive)
                  _Banner(
                    icon: Icons.warning_amber_rounded,
                    color: AppTheme.warn,
                    text:
                        'Low confidence — the top scores are very close. Treat this as tentative and seek confirmation.',
                  ),
                Row(
                  children: [
                    Expanded(
                      child: _Metric(
                        label: 'Crop',
                        value: result.cropName,
                        confidence: result.cropConfidence,
                        color: AppTheme.corn,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _Metric(
                        label: 'Disease',
                        value: result.diseaseName,
                        confidence: result.diseaseConfidence,
                        color: AppTheme.disease,
                      ),
                    ),
                  ],
                ),
                if (result.cropWasAssumed)
                  _caption(context, 'Grape was assumed — no Corn detection found.'),
                if (result.diseaseWasFallback)
                  _caption(context,
                      'Healthy fallback applied — no qualifying disease detected.'),
                if (result.scores.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  Text('Detected classes',
                      style: Theme.of(context).textTheme.labelLarge),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final s in result.scores)
                        Chip(
                          label: Text(
                              '${s.className}  ${(s.confidence * 100).toStringAsFixed(1)}%'),
                          visualDensity: VisualDensity.compact,
                        ),
                    ],
                  ),
                ],
                if (result.recommendation != null &&
                    result.recommendation!.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.corn.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.eco_outlined,
                            color: AppTheme.corn, size: 20),
                        const SizedBox(width: 8),
                        Expanded(child: Text(result.recommendation!)),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _caption(BuildContext context, String text) => Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Text(text,
            style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                fontStyle: FontStyle.italic)),
      );
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;
  final double confidence;
  final Color color;
  const _Metric({
    required this.label,
    required this.value,
    required this.confidence,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label.toUpperCase(),
              style: TextStyle(
                  fontSize: 11,
                  letterSpacing: 0.5,
                  color: scheme.onSurfaceVariant,
                  fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Text(value,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: confidence.clamp(0.0, 1.0),
              minHeight: 6,
              backgroundColor: color.withValues(alpha: 0.15),
              valueColor: AlwaysStoppedAnimation(color),
            ),
          ),
          const SizedBox(height: 4),
          Text('${(confidence * 100).toStringAsFixed(1)}%',
              style: TextStyle(fontSize: 12, color: scheme.onSurfaceVariant)),
        ],
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String text;
  const _Banner({required this.icon, required this.color, required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 13))),
        ],
      ),
    );
  }
}
