import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../models/medicine.dart';
import '../providers/medicines_provider.dart';
import 'severity_chart.dart';

const _methods = ['Foliar Spray', 'Soil Drench', 'Seed Treatment', 'Other'];

/// Medicine tracker: list of treatment entries, add form, and severity chart.
class TrackerPanel extends ConsumerWidget {
  final String sessionId;
  const TrackerPanel({super.key, required this.sessionId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(medicinesProvider(sessionId));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.medication_outlined, size: 20),
            const SizedBox(width: 8),
            Text('Treatment Tracker',
                style: Theme.of(context).textTheme.titleMedium),
            const Spacer(),
            FilledButton.tonalIcon(
              onPressed: () => _openAddDialog(context, ref, async.valueOrNull ?? []),
              icon: const Icon(Icons.add, size: 18),
              label: const Text('Add'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        async.when(
          loading: () => const Padding(
            padding: EdgeInsets.all(24),
            child: Center(child: CircularProgressIndicator()),
          ),
          error: (e, _) => Text('Could not load entries: $e'),
          data: (entries) {
            if (entries.isEmpty) {
              return _empty(context);
            }
            return Column(
              children: [
                for (final m in entries) _MedicineTile(sessionId: sessionId, medicine: m),
                const SizedBox(height: 12),
                SeverityChart(entries: entries),
              ],
            );
          },
        ),
      ],
    );
  }

  Widget _empty(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Text(
          'No treatments logged yet. Add this week\'s treatment to start tracking progress.',
          style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
        ),
      );

  Future<void> _openAddDialog(
      BuildContext context, WidgetRef ref, List<Medicine> existing) async {
    final nextWeek = existing.isEmpty
        ? 1
        : (existing.map((e) => e.weekNumber).reduce((a, b) => a > b ? a : b) + 1);
    final result = await showDialog<Medicine>(
      context: context,
      builder: (_) => _AddMedicineDialog(initialWeek: nextWeek),
    );
    if (result != null) {
      await ref.read(medicinesProvider(sessionId).notifier).add(result);
    }
  }
}

class _MedicineTile extends ConsumerWidget {
  final String sessionId;
  final Medicine medicine;
  const _MedicineTile({required this.sessionId, required this.medicine});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Container(
              width: 42,
              height: 42,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: scheme.primary.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text('W${medicine.weekNumber}',
                  style: TextStyle(
                      fontWeight: FontWeight.w700, color: scheme.primary)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(medicine.medicineName,
                      style: const TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 2),
                  Text(
                    [
                      if (medicine.dosageApplied.isNotEmpty) medicine.dosageApplied,
                      medicine.applicationMethod,
                      DateFormat.yMMMd().format(medicine.dateApplied),
                    ].join(' · '),
                    style: TextStyle(fontSize: 12, color: scheme.onSurfaceVariant),
                  ),
                  if (medicine.notes.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(medicine.notes,
                          style: TextStyle(
                              fontSize: 12,
                              fontStyle: FontStyle.italic,
                              color: scheme.onSurfaceVariant)),
                    ),
                ],
              ),
            ),
            _SeverityDot(severity: medicine.symptomSeverity),
            IconButton(
              icon: const Icon(Icons.delete_outline, size: 20),
              tooltip: 'Delete',
              onPressed: () => ref
                  .read(medicinesProvider(sessionId).notifier)
                  .remove(medicine.entryId!),
            ),
          ],
        ),
      ),
    );
  }
}

class _SeverityDot extends StatelessWidget {
  final int severity;
  const _SeverityDot({required this.severity});

  @override
  Widget build(BuildContext context) {
    final colors = [
      Colors.green,
      Colors.lightGreen,
      Colors.amber,
      Colors.orange,
      Colors.red,
    ];
    final c = colors[(severity - 1).clamp(0, 4)];
    return Tooltip(
      message: 'Severity $severity / 5',
      child: Container(
        width: 28,
        height: 28,
        alignment: Alignment.center,
        decoration: BoxDecoration(color: c.withValues(alpha: 0.18), shape: BoxShape.circle),
        child: Text('$severity',
            style: TextStyle(color: c, fontWeight: FontWeight.w700, fontSize: 13)),
      ),
    );
  }
}

class _AddMedicineDialog extends StatefulWidget {
  final int initialWeek;
  const _AddMedicineDialog({required this.initialWeek});

  @override
  State<_AddMedicineDialog> createState() => _AddMedicineDialogState();
}

class _AddMedicineDialogState extends State<_AddMedicineDialog> {
  final _name = TextEditingController();
  final _dosage = TextEditingController();
  final _notes = TextEditingController();
  late int _week = widget.initialWeek;
  String _method = _methods.first;
  int _severity = 3;
  final DateTime _date = DateTime.now();

  @override
  void dispose() {
    _name.dispose();
    _dosage.dispose();
    _notes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add treatment'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _name,
              decoration: const InputDecoration(labelText: 'Medicine name *'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _dosage,
              decoration: const InputDecoration(labelText: 'Dosage (e.g. 2 ml/L)'),
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: _method,
              decoration: const InputDecoration(labelText: 'Method'),
              items: [
                for (final m in _methods)
                  DropdownMenuItem(value: m, child: Text(m)),
              ],
              onChanged: (v) => setState(() => _method = v ?? _method),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: Row(
                    children: [
                      const Text('Week '),
                      IconButton(
                        onPressed: () => setState(() => _week = (_week - 1).clamp(1, 999)),
                        icon: const Icon(Icons.remove_circle_outline),
                      ),
                      Text('$_week', style: const TextStyle(fontWeight: FontWeight.bold)),
                      IconButton(
                        onPressed: () => setState(() => _week += 1),
                        icon: const Icon(Icons.add_circle_outline),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            Row(
              children: [
                const Text('Severity '),
                Expanded(
                  child: Slider(
                    value: _severity.toDouble(),
                    min: 1,
                    max: 5,
                    divisions: 4,
                    label: '$_severity',
                    onChanged: (v) => setState(() => _severity = v.round()),
                  ),
                ),
                Text('$_severity/5'),
              ],
            ),
            TextField(
              controller: _notes,
              decoration: const InputDecoration(labelText: 'Notes'),
              maxLines: 2,
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(
          onPressed: () {
            if (_name.text.trim().isEmpty) return;
            Navigator.pop(
              context,
              Medicine(
                weekNumber: _week,
                dateApplied: _date,
                medicineName: _name.text.trim(),
                dosageApplied: _dosage.text.trim(),
                applicationMethod: _method,
                symptomSeverity: _severity,
                notes: _notes.text.trim(),
              ),
            );
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}
