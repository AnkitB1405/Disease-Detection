import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../models/session.dart';
import '../providers/active_session_provider.dart';
import '../providers/providers.dart';
import '../providers/sessions_provider.dart';

/// Browse, switch, and delete past sessions.
class SessionsScreen extends ConsumerWidget {
  const SessionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(sessionsProvider);
    final activeId = ref.watch(activeSessionProvider).id;

    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Could not load sessions: $e')),
      data: (sessions) {
        if (sessions.isEmpty) {
          return const Center(child: Text('No sessions yet.'));
        }
        return ListView.separated(
          padding: const EdgeInsets.all(16),
          itemCount: sessions.length,
          separatorBuilder: (_, _) => const SizedBox(height: 8),
          itemBuilder: (_, i) {
            final s = sessions[i];
            return _SessionTile(
              session: s,
              active: s.sessionId == activeId,
              onOpen: () async {
                await ref.read(activeSessionProvider.notifier).select(s);
                ref.read(appModeProvider.notifier).state =
                    s.hasAnalysis || (s.diseaseName?.isNotEmpty ?? false)
                        ? AppMode.chat
                        : AppMode.onboarding;
              },
              onDelete: () async {
                await ref.read(sessionsProvider.notifier).remove(s.sessionId);
                if (s.sessionId == activeId) {
                  ref.read(activeSessionProvider.notifier).clear();
                  ref.read(appModeProvider.notifier).state = AppMode.onboarding;
                }
              },
            );
          },
        );
      },
    );
  }
}

class _SessionTile extends StatelessWidget {
  final Session session;
  final bool active;
  final VoidCallback onOpen;
  final VoidCallback onDelete;

  const _SessionTile({
    required this.session,
    required this.active,
    required this.onOpen,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: active ? scheme.primaryContainer.withValues(alpha: 0.5) : null,
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        leading: CircleAvatar(
          backgroundColor: scheme.primary.withValues(alpha: 0.15),
          child: Icon(Icons.eco_outlined, color: scheme.primary),
        ),
        title: Text(session.displayName,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(
          [
            if (session.cropName != null) session.cropName!,
            if (session.diseaseName != null) session.diseaseName!,
            DateFormat.yMMMd().format(session.createdAt),
          ].join(' · '),
        ),
        trailing: IconButton(
          icon: const Icon(Icons.delete_outline),
          onPressed: () => _confirmDelete(context),
        ),
        onTap: onOpen,
      ),
    );
  }

  Future<void> _confirmDelete(BuildContext context) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete session?'),
        content: Text('"${session.displayName}" and its treatment log will be removed.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Delete')),
        ],
      ),
    );
    if (ok == true) onDelete();
  }
}
