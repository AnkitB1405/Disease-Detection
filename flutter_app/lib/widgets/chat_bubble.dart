import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

import '../models/chat_message.dart';

/// A single chat message. Assistant messages render markdown (medicine tables,
/// treatment text); user messages render plain text.
class ChatBubble extends StatelessWidget {
  final ChatMessage message;
  const ChatBubble({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isUser = message.isUser;
    final bg = isUser ? scheme.primary : scheme.surfaceContainerHighest;
    final fg = isUser ? scheme.onPrimary : scheme.onSurface;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 560),
        margin: const EdgeInsets.symmetric(vertical: 5),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(isUser ? 18 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 18),
          ),
        ),
        child: isUser
            ? Text(message.content, style: TextStyle(color: fg, height: 1.35))
            : _AssistantBody(message: message, color: fg),
      ),
    );
  }
}

class _AssistantBody extends StatelessWidget {
  final ChatMessage message;
  final Color color;
  const _AssistantBody({required this.message, required this.color});

  @override
  Widget build(BuildContext context) {
    if (message.content.isEmpty && message.streaming) {
      return const SizedBox(
        height: 18,
        width: 18,
        child: CircularProgressIndicator(strokeWidth: 2),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        MarkdownBody(
          data: message.content,
          shrinkWrap: true,
          styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
            p: TextStyle(color: color, height: 1.4),
            tableBorder: TableBorder.all(
              color: Theme.of(context).colorScheme.outlineVariant,
              width: 1,
            ),
            tableCellsPadding: const EdgeInsets.all(6),
          ),
        ),
        if (message.streaming)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text('▍',
                style: TextStyle(color: color.withValues(alpha: 0.5))),
          ),
      ],
    );
  }
}
