import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/medicine.dart';
import 'providers.dart';

/// Medicine-tracker entries for one session (loaded from SQLite via the API).
class MedicinesNotifier extends FamilyAsyncNotifier<List<Medicine>, String> {
  @override
  Future<List<Medicine>> build(String sessionId) {
    return ref.read(apiClientProvider).listMedicines(sessionId);
  }

  Future<void> add(Medicine medicine) async {
    await ref.read(apiClientProvider).addMedicine(arg, medicine);
    ref.invalidateSelf();
    await future;
  }

  Future<void> edit(String entryId, Medicine medicine) async {
    await ref.read(apiClientProvider).updateMedicine(arg, entryId, medicine);
    ref.invalidateSelf();
    await future;
  }

  Future<void> remove(String entryId) async {
    await ref.read(apiClientProvider).deleteMedicine(arg, entryId);
    ref.invalidateSelf();
    await future;
  }
}

final medicinesProvider = AsyncNotifierProvider.family<MedicinesNotifier,
    List<Medicine>, String>(MedicinesNotifier.new);
