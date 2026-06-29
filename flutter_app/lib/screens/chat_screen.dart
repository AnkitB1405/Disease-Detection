import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/active_session_provider.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/detection_card.dart';
import '../widgets/tracker_panel.dart';

/// Combined treatment / clarification chat. Shows the detection result and
/// medicine tracker once a diagnosis exists, plus the streaming conversation.
class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _send() {
    final text = _input.text.trim();
    if (text.isEmpty) return;
    _input.clear();
    ref.read(activeSessionProvider.notifier).sendMessage(text);
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(activeSessionProvider);
    ref.listen(activeSessionProvider, (_, _) => _scrollToBottom());

    final hasDiagnosis = state.analysis != null ||
        (state.diseaseName != null && state.diseaseName!.isNotEmpty);

    return Column(
      children: [
        Expanded(
          child: ListView(
            controller: _scroll,
            padding: const EdgeInsets.all(16),
            children: [
              if (state.analysis != null) ...[
                DetectionCard(result: state.analysis!),
                const SizedBox(height: 16),
              ],
              if (state.messages.isEmpty && state.analysis == null && !state.busy)
                _emptyHint(context),
              for (final m in state.messages) ChatBubble(message: m),
              if (hasDiagnosis && state.id != null) ...[
                const SizedBox(height: 20),
                const Divider(),
                const SizedBox(height: 8),
                TrackerPanel(sessionId: state.id!),
              ],
            ],
          ),
        ),
        _InputBar(controller: _input, busy: state.busy, onSend: _send),
      ],
    );
  }

  Widget _emptyHint(BuildContext context) => Container(
        margin: const EdgeInsets.only(top: 40),
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Icon(Icons.eco_outlined,
                size: 44, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 12),
            Text('Describe the symptoms you see',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(
              'For example: which part of the plant is affected, the colour or '
              'pattern, and how long it has been like this.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
            ),
          ],
        ),
      );
}

class _InputBar extends StatelessWidget {
  final TextEditingController controller;
  final bool busy;
  final VoidCallback onSend;
  const _InputBar(
      {required this.controller, required this.busy, required this.onSend});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 6, 12, 12),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => busy ? null : onSend(),
                decoration: const InputDecoration(
                  hintText: 'Type a message…',
                ),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(
              onPressed: busy ? null : onSend,
              style: FilledButton.styleFrom(
                shape: const CircleBorder(),
                padding: const EdgeInsets.all(16),
              ),
              child: busy
                  ? const SizedBox(
                      width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.send),
            ),
          ],
        ),
      ),
    );
  }
}
