import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/analysis.dart';
import '../models/chat_message.dart';
import '../models/session.dart';
import 'providers.dart';

class ActiveSessionState {
  final String? id;
  final String displayName;
  final List<ChatMessage> messages;
  final AnalysisResult? analysis;
  final String? cropName;
  final String? diseaseName;
  final bool busy; // a Groq call / analysis is in flight

  const ActiveSessionState({
    this.id,
    this.displayName = '',
    this.messages = const [],
    this.analysis,
    this.cropName,
    this.diseaseName,
    this.busy = false,
  });

  bool get hasSession => id != null;

  ActiveSessionState copyWith({
    String? id,
    String? displayName,
    List<ChatMessage>? messages,
    AnalysisResult? analysis,
    bool clearAnalysis = false,
    String? cropName,
    String? diseaseName,
    bool? busy,
  }) {
    return ActiveSessionState(
      id: id ?? this.id,
      displayName: displayName ?? this.displayName,
      messages: messages ?? this.messages,
      analysis: clearAnalysis ? null : (analysis ?? this.analysis),
      cropName: cropName ?? this.cropName,
      diseaseName: diseaseName ?? this.diseaseName,
      busy: busy ?? this.busy,
    );
  }
}

/// Holds the live UI state for the currently selected session: chat messages,
/// the last analysis, and streaming flags. Mirrors what st.session_state held
/// per active session in the Streamlit app.
class ActiveSessionNotifier extends Notifier<ActiveSessionState> {
  @override
  ActiveSessionState build() => const ActiveSessionState();

  void _emit() => state = state.copyWith(messages: List.of(state.messages));

  Future<void> select(Session session) async {
    state = ActiveSessionState(
      id: session.sessionId,
      displayName: session.displayName,
      cropName: session.cropName,
      diseaseName: session.diseaseName,
      busy: true,
    );
    try {
      final detail = await ref.read(apiClientProvider).getSession(session.sessionId);
      state = state.copyWith(
        messages: detail.chatHistory,
        cropName: detail.cropName,
        diseaseName: detail.diseaseName,
        busy: false,
      );
    } catch (_) {
      state = state.copyWith(busy: false);
    }
  }

  void clear() => state = const ActiveSessionState();

  /// Upload/camera path: run analysis, then stream the Phase-2 summary.
  Future<void> analyze(Uint8List bytes, String filename, {String note = ''}) async {
    final id = state.id;
    if (id == null) return;
    state = state.copyWith(busy: true);
    final api = ref.read(apiClientProvider);
    try {
      final result = await api.analyze(
        sessionId: id, bytes: bytes, filename: filename, note: note,
      );
      final msgs = List.of(state.messages);
      if (result.medicineTableMd.isNotEmpty) {
        msgs.add(ChatMessage(role: 'assistant', content: result.medicineTableMd));
      }
      state = state.copyWith(
        analysis: result,
        messages: msgs,
        cropName: result.cropName,
        diseaseName: result.diseaseName,
      );
      await _consume(api.summaryStream(id));
    } catch (e) {
      _appendAssistant('⚠ Analysis failed: $e');
    } finally {
      state = state.copyWith(busy: false);
    }
  }

  /// Send a text message (clarification or follow-up); stream the reply.
  Future<void> sendMessage(String text) async {
    final id = state.id;
    if (id == null || text.trim().isEmpty) return;
    final msgs = List.of(state.messages)
      ..add(ChatMessage(role: 'user', content: text.trim()));
    state = state.copyWith(messages: msgs, busy: true);
    try {
      await _consume(ref.read(apiClientProvider).messageStream(id, text.trim()));
    } catch (e) {
      _appendAssistant('⚠ $e');
    } finally {
      state = state.copyWith(busy: false);
    }
  }

  /// Drain an SSE stream into a single streaming assistant bubble.
  Future<void> _consume(Stream stream) async {
    final bubble = ChatMessage(role: 'assistant', content: '', streaming: true);
    final msgs = List.of(state.messages)..add(bubble);
    state = state.copyWith(messages: msgs);
    await for (final ev in stream) {
      switch (ev.type) {
        case 'token':
        case 'question':
          bubble.content += ev.content as String;
          _emit();
          break;
        case 'error':
          bubble.content += '\n\n⚠ ${ev.content}';
          _emit();
          break;
        case 'done':
          break;
      }
    }
    bubble.streaming = false;
    if (bubble.content.trim().isEmpty) {
      final m = List.of(state.messages)..remove(bubble);
      state = state.copyWith(messages: m);
    } else {
      _emit();
    }
  }

  void _appendAssistant(String content) {
    final msgs = List.of(state.messages)
      ..add(ChatMessage(role: 'assistant', content: content));
    state = state.copyWith(messages: msgs);
  }
}

final activeSessionProvider =
    NotifierProvider<ActiveSessionNotifier, ActiveSessionState>(
        ActiveSessionNotifier.new);
