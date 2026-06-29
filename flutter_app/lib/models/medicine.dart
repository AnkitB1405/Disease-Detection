import 'package:intl/intl.dart';

class Medicine {
  final String? entryId;
  final String? sessionId;
  final int weekNumber;
  final DateTime dateApplied;
  final String medicineId;
  final String medicineName;
  final String dosageApplied;
  final String applicationMethod;
  final int symptomSeverity;
  final String notes;
  final bool? isImproving;

  const Medicine({
    this.entryId,
    this.sessionId,
    required this.weekNumber,
    required this.dateApplied,
    this.medicineId = 'manual',
    required this.medicineName,
    this.dosageApplied = '',
    this.applicationMethod = 'Other',
    this.symptomSeverity = 3,
    this.notes = '',
    this.isImproving,
  });

  factory Medicine.fromJson(Map<String, dynamic> j) => Medicine(
        entryId: j['entry_id'] as String?,
        sessionId: j['session_id'] as String?,
        weekNumber: j['week_number'] as int,
        dateApplied: DateTime.parse(j['date_applied'] as String),
        medicineId: j['medicine_id'] as String? ?? 'manual',
        medicineName: j['medicine_name'] as String,
        dosageApplied: j['dosage_applied'] as String? ?? '',
        applicationMethod: j['application_method'] as String? ?? 'Other',
        symptomSeverity: j['symptom_severity'] as int? ?? 3,
        notes: j['notes'] as String? ?? '',
        isImproving: j['is_improving'] as bool?,
      );

  Map<String, dynamic> toCreateJson() => {
        'week_number': weekNumber,
        'date_applied': DateFormat('yyyy-MM-dd').format(dateApplied),
        'medicine_name': medicineName,
        'dosage_applied': dosageApplied,
        'application_method': applicationMethod,
        'symptom_severity': symptomSeverity,
        'notes': notes,
        'is_improving': isImproving,
      };
}
