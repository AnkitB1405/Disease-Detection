import 'chat_message.dart';

class Session {
  final String sessionId;
  final String displayName;
  final String? cropName;
  final String? diseaseName;
  final DateTime createdAt;
  final bool hasAnalysis;

  const Session({
    required this.sessionId,
    required this.displayName,
    required this.cropName,
    required this.diseaseName,
    required this.createdAt,
    required this.hasAnalysis,
  });

  factory Session.fromJson(Map<String, dynamic> j) => Session(
        sessionId: j['session_id'] as String,
        displayName: j['display_name'] as String,
        cropName: j['crop_name'] as String?,
        diseaseName: j['disease_name'] as String?,
        createdAt: DateTime.parse(j['created_at'] as String),
        hasAnalysis: j['has_analysis'] as bool? ?? false,
      );
}

class SessionDetail extends Session {
  final String mode;
  final List<ChatMessage> chatHistory;

  const SessionDetail({
    required super.sessionId,
    required super.displayName,
    required super.cropName,
    required super.diseaseName,
    required super.createdAt,
    required super.hasAnalysis,
    required this.mode,
    required this.chatHistory,
  });

  factory SessionDetail.fromJson(Map<String, dynamic> j) => SessionDetail(
        sessionId: j['session_id'] as String,
        displayName: j['display_name'] as String,
        cropName: j['crop_name'] as String?,
        diseaseName: j['disease_name'] as String?,
        createdAt: DateTime.parse(j['created_at'] as String),
        hasAnalysis: j['has_analysis'] as bool? ?? false,
        mode: j['mode'] as String? ?? 'ONBOARDING',
        chatHistory: (j['chat_history'] as List<dynamic>? ?? [])
            .map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}
