import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';

/// Which screen the shell shows for the active session.
enum AppMode { onboarding, upload, camera, chat, sessions }

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

final appModeProvider =
    StateProvider<AppMode>((ref) => AppMode.onboarding);
