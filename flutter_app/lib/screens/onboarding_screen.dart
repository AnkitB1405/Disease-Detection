import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme.dart';
import '../providers/providers.dart';
import '../widgets/option_card.dart';

class OnboardingScreen extends ConsumerWidget {
  const OnboardingScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('How would you like to start?',
            style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 6),
        Text(
          'Identify a crop disease, then get a treatment plan and track progress.',
          style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
        ),
        const SizedBox(height: 20),
        OptionCard(
          icon: Icons.image_outlined,
          title: 'Upload a photo',
          subtitle: 'Pick a leaf image from your device for analysis.',
          color: AppTheme.corn,
          onTap: () => ref.read(appModeProvider.notifier).state = AppMode.upload,
        ),
        const SizedBox(height: 12),
        OptionCard(
          icon: Icons.videocam_outlined,
          title: 'Live camera',
          subtitle: 'Point your camera at a leaf with real-time detection.',
          color: AppTheme.seed,
          onTap: () => ref.read(appModeProvider.notifier).state = AppMode.camera,
        ),
        const SizedBox(height: 12),
        OptionCard(
          icon: Icons.chat_bubble_outline,
          title: 'Describe symptoms',
          subtitle: 'No photo? Answer a few questions to get guidance.',
          color: AppTheme.warn,
          onTap: () => ref.read(appModeProvider.notifier).state = AppMode.chat,
        ),
      ],
    );
  }
}
