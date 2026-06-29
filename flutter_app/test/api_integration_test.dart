// Live integration test for the Flutter networking layer against the FastAPI
// backend. It is skipped by default so the normal `flutter test` run stays
// green without a server. To run it:
//
//   1. python server.py            (in the repo root, any port)
//   2. flutter test --dart-define=RUN_INTEGRATION=true \
//        --dart-define=API_HOST=127.0.0.1 --dart-define=API_PORT=8000 \
//        test/api_integration_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:crop_disease_app/core/api_client.dart';
import 'package:crop_disease_app/models/medicine.dart';

const _run = bool.fromEnvironment('RUN_INTEGRATION', defaultValue: false);

void main() {
  test('ApiClient round-trips sessions + medicines against live backend',
      () async {
    final api = ApiClient();
    final created = await api.createSession('IntegrationTest');
    expect(created.sessionId, isNotEmpty);

    final list = await api.listSessions();
    expect(list.any((s) => s.sessionId == created.sessionId), isTrue);

    final med = await api.addMedicine(created.sessionId, Medicine(
      weekNumber: 1,
      dateApplied: DateTime(2026, 6, 29),
      medicineName: 'Test Fungicide',
      dosageApplied: '2 ml/L',
      applicationMethod: 'Foliar Spray',
      symptomSeverity: 3,
      notes: 'integration',
    ));
    expect(med.medicineId, 'manual');

    final meds = await api.listMedicines(created.sessionId);
    expect(meds.length, 1);

    final detail = await api.getSession(created.sessionId);
    expect(detail.mode, isNotEmpty);

    await api.deleteSession(created.sessionId);
  }, skip: _run ? false : 'Set --dart-define=RUN_INTEGRATION=true with backend running');
}
