class ChatMessage {
  final String role; // "user" | "assistant"
  String content;
  bool streaming;

  ChatMessage({
    required this.role,
    required this.content,
    this.streaming = false,
  });

  bool get isUser => role == 'user';

  factory ChatMessage.fromJson(Map<String, dynamic> j) => ChatMessage(
        role: j['role'] as String,
        content: j['content'] as String,
      );
}
