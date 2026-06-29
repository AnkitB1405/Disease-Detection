import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../models/medicine.dart';

/// Bar chart of the maximum recorded symptom severity per week.
/// Mirrors tracker_ui._render_sparkline (needs >= 2 weeks of data).
class SeverityChart extends StatelessWidget {
  final List<Medicine> entries;
  const SeverityChart({super.key, required this.entries});

  @override
  Widget build(BuildContext context) {
    final Map<int, int> maxByWeek = {};
    for (final e in entries) {
      maxByWeek.update(e.weekNumber, (v) => v > e.symptomSeverity ? v : e.symptomSeverity,
          ifAbsent: () => e.symptomSeverity);
    }
    if (maxByWeek.length < 2) return const SizedBox.shrink();

    final weeks = maxByWeek.keys.toList()..sort();
    final scheme = Theme.of(context).colorScheme;

    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Symptom severity by week',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 16),
            SizedBox(
              height: 160,
              child: BarChart(
                BarChartData(
                  maxY: 5,
                  minY: 0,
                  borderData: FlBorderData(show: false),
                  gridData: const FlGridData(show: true, drawVerticalLine: false),
                  titlesData: FlTitlesData(
                    topTitles:
                        const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    rightTitles:
                        const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    leftTitles: const AxisTitles(
                      sideTitles: SideTitles(
                          showTitles: true, reservedSize: 28, interval: 1),
                    ),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        getTitlesWidget: (value, meta) {
                          final i = value.toInt();
                          if (i < 0 || i >= weeks.length) return const SizedBox();
                          return Padding(
                            padding: const EdgeInsets.only(top: 6),
                            child: Text('W${weeks[i]}',
                                style: const TextStyle(fontSize: 11)),
                          );
                        },
                      ),
                    ),
                  ),
                  barGroups: [
                    for (var i = 0; i < weeks.length; i++)
                      BarChartGroupData(x: i, barRods: [
                        BarChartRodData(
                          toY: maxByWeek[weeks[i]]!.toDouble(),
                          width: 18,
                          color: scheme.primary,
                          borderRadius: const BorderRadius.vertical(
                              top: Radius.circular(6)),
                        ),
                      ]),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 4),
            Text('Lower is better — track whether treatment is helping.',
                style: TextStyle(
                    fontSize: 12, color: AppTheme.corn, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}
