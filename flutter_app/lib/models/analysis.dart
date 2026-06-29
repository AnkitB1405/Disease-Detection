import 'medicine.dart';

class DetectionScore {
  final String className;
  final double confidence;
  const DetectionScore(this.className, this.confidence);

  factory DetectionScore.fromJson(Map<String, dynamic> j) =>
      DetectionScore(j['class_name'] as String, (j['confidence'] as num).toDouble());
}

class AnalysisResult {
  final String cropName;
  final double cropConfidence;
  final bool cropWasAssumed;
  final String diseaseName;
  final double diseaseConfidence;
  final bool diseaseWasFallback;
  final String? recommendation;
  final bool inconclusive;
  final String annotatedUrl;
  final List<DetectionScore> scores;
  final String medicineTableMd;
  final List<Medicine> medicines;

  const AnalysisResult({
    required this.cropName,
    required this.cropConfidence,
    required this.cropWasAssumed,
    required this.diseaseName,
    required this.diseaseConfidence,
    required this.diseaseWasFallback,
    required this.recommendation,
    required this.inconclusive,
    required this.annotatedUrl,
    required this.scores,
    required this.medicineTableMd,
    required this.medicines,
  });

  factory AnalysisResult.fromJson(Map<String, dynamic> j) => AnalysisResult(
        cropName: j['crop_name'] as String,
        cropConfidence: (j['crop_confidence'] as num).toDouble(),
        cropWasAssumed: j['crop_was_assumed'] as bool? ?? false,
        diseaseName: j['disease_name'] as String,
        diseaseConfidence: (j['disease_confidence'] as num).toDouble(),
        diseaseWasFallback: j['disease_was_fallback'] as bool? ?? false,
        recommendation: j['recommendation'] as String?,
        inconclusive: j['inconclusive'] as bool? ?? false,
        annotatedUrl: j['annotated_url'] as String,
        scores: (j['scores'] as List<dynamic>? ?? [])
            .map((e) => DetectionScore.fromJson(e as Map<String, dynamic>))
            .toList(),
        medicineTableMd: j['medicine_table_md'] as String? ?? '',
        medicines: (j['medicines'] as List<dynamic>? ?? [])
            .map((e) => Medicine.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

/// Live camera preview detection box returned over WebSocket.
class CameraDetection {
  final List<double>? box; // [x1,y1,x2,y2] in source pixels, or null
  final String label;
  final double confidence;
  final int width;
  final int height;

  const CameraDetection({
    required this.box,
    required this.label,
    required this.confidence,
    required this.width,
    required this.height,
  });

  factory CameraDetection.fromJson(Map<String, dynamic> j) => CameraDetection(
        box: (j['box'] as List<dynamic>?)?.map((e) => (e as num).toDouble()).toList(),
        label: j['label'] as String? ?? '',
        confidence: (j['confidence'] as num?)?.toDouble() ?? 0.0,
        width: j['width'] as int? ?? 0,
        height: j['height'] as int? ?? 0,
      );
}
