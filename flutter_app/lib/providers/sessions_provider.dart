import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/session.dart';
import 'providers.dart';

/// Loads and mutates the list of crop sessions (sidebar).
class SessionsNotifier extends AsyncNotifier<List<Session>> {
  @override
  Future<List<Session>> build() async {
    return ref.read(apiClientProvider).listSessions();
  }

  Future<Session> create(String displayName) async {
    final session = await ref.read(apiClientProvider).createSession(displayName);
    state = await AsyncValue.guard(() => ref.read(apiClientProvider).listSessions());
    return session;
  }

  Future<void> remove(String sessionId) async {
    await ref.read(apiClientProvider).deleteSession(sessionId);
    state = await AsyncValue.guard(() => ref.read(apiClientProvider).listSessions());
  }

  Future<void> refresh() async {
    state = await AsyncValue.guard(() => ref.read(apiClientProvider).listSessions());
  }
}

final sessionsProvider =
    AsyncNotifierProvider<SessionsNotifier, List<Session>>(SessionsNotifier.new);
