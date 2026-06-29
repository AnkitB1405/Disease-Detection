// Basic smoke test for the Crop Disease app shell.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:crop_disease_app/screens/home_shell.dart';

void main() {
  testWidgets('shows welcome when no session', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: MaterialApp(home: HomeShell())));
    expect(find.text('Create a session'), findsOneWidget);
  });
}
