import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/active_session_provider.dart';
import '../providers/providers.dart';
import '../providers/sessions_provider.dart';
import 'camera_screen.dart';
import 'chat_screen.dart';
import 'onboarding_screen.dart';
import 'sessions_screen.dart';
import 'upload_screen.dart';

class HomeShell extends ConsumerWidget {
  const HomeShell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final active = ref.watch(activeSessionProvider);
    final mode = ref.watch(appModeProvider);

    final title = !active.hasSession
        ? 'Crop Disease Detection'
        : active.displayName;

    return Scaffold(
      appBar: AppBar(
        title: Text(title, overflow: TextOverflow.ellipsis),
        actions: [
          if (active.hasSession && mode != AppMode.onboarding)
            IconButton(
              tooltip: 'Home',
              icon: const Icon(Icons.home_outlined),
              onPressed: () =>
                  ref.read(appModeProvider.notifier).state = AppMode.onboarding,
            ),
          IconButton(
            tooltip: 'New session',
            icon: const Icon(Icons.add_circle_outline),
            onPressed: () => _newSessionDialog(context, ref),
          ),
        ],
      ),
      drawer: const _SessionsDrawer(),
      body: !active.hasSession
          ? _Welcome(onCreate: () => _newSessionDialog(context, ref))
          : switch (mode) {
              AppMode.onboarding => const OnboardingScreen(),
              AppMode.upload => const UploadScreen(),
              AppMode.camera => const CameraScreen(),
              AppMode.chat => const ChatScreen(),
              AppMode.sessions => const SessionsScreen(),
            },
    );
  }
}

Future<void> _newSessionDialog(BuildContext context, WidgetRef ref) async {
  final controller = TextEditingController(text: 'Field ${DateTime.now().day}');
  final name = await showDialog<String>(
    context: context,
    builder: (_) => AlertDialog(
      title: const Text('New session'),
      content: TextField(
        controller: controller,
        autofocus: true,
        decoration: const InputDecoration(
          labelText: 'Name',
          hintText: 'e.g. Corn Field A',
        ),
        onSubmitted: (v) => Navigator.pop(context, v),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('Create')),
      ],
    ),
  );
  if (name == null || name.trim().isEmpty) return;
  final session = await ref.read(sessionsProvider.notifier).create(name.trim());
  await ref.read(activeSessionProvider.notifier).select(session);
  ref.read(appModeProvider.notifier).state = AppMode.onboarding;
}

class _Welcome extends StatelessWidget {
  final VoidCallback onCreate;
  const _Welcome({required this.onCreate});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 84,
              height: 84,
              decoration: BoxDecoration(
                color: scheme.primary.withValues(alpha: 0.12),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.eco, size: 42, color: scheme.primary),
            ),
            const SizedBox(height: 20),
            Text('Welcome', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text(
              'Create a session for a crop or field to detect diseases, get a '
              'treatment plan, and track recovery week by week.',
              textAlign: TextAlign.center,
              style: TextStyle(color: scheme.onSurfaceVariant),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: onCreate,
              icon: const Icon(Icons.add),
              label: const Text('Create a session'),
            ),
          ],
        ),
      ),
    );
  }
}

class _SessionsDrawer extends ConsumerWidget {
  const _SessionsDrawer();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(sessionsProvider);
    final activeId = ref.watch(activeSessionProvider).id;
    final scheme = Theme.of(context).colorScheme;

    return Drawer(
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
              child: Row(
                children: [
                  Icon(Icons.eco, color: scheme.primary),
                  const SizedBox(width: 10),
                  Text('Sessions',
                      style: Theme.of(context).textTheme.titleLarge),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: FilledButton.tonalIcon(
                onPressed: () {
                  Navigator.pop(context);
                  _newSessionDialog(context, ref);
                },
                icon: const Icon(Icons.add),
                label: const Text('New session'),
                style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(44)),
              ),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: async.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text('Backend unreachable.\n$e',
                      style: TextStyle(color: scheme.error)),
                ),
                data: (sessions) => ListView(
                  children: [
                    for (final s in sessions)
                      ListTile(
                        selected: s.sessionId == activeId,
                        selectedTileColor: scheme.primaryContainer.withValues(alpha: 0.4),
                        leading: const Icon(Icons.spa_outlined),
                        title: Text(s.displayName,
                            maxLines: 1, overflow: TextOverflow.ellipsis),
                        subtitle: s.diseaseName != null
                            ? Text(s.diseaseName!,
                                maxLines: 1, overflow: TextOverflow.ellipsis)
                            : null,
                        onTap: () async {
                          Navigator.pop(context);
                          await ref.read(activeSessionProvider.notifier).select(s);
                          ref.read(appModeProvider.notifier).state =
                              (s.diseaseName?.isNotEmpty ?? false)
                                  ? AppMode.chat
                                  : AppMode.onboarding;
                        },
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
