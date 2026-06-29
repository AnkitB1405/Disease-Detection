import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../models/analysis.dart';
import '../models/medicine.dart';
import '../models/session.dart';
import 'config.dart';
import 'sse.dart';

/// Single gateway to the FastAPI backend: REST (dio), SSE, and URL builders.
class ApiClient {
  ApiClient() : _dio = Dio(BaseOptions(
          baseUrl: ApiConfig.baseUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 180),
        ));

  final Dio _dio;

  // ----- Sessions ------------------------------------------------------- //
  Future<List<Session>> listSessions() async {
    final r = await _dio.get('/api/sessions');
    return (r.data as List).map((e) => Session.fromJson(e)).toList();
  }

  Future<Session> createSession(String displayName) async {
    final r = await _dio.post('/api/sessions', data: {'display_name': displayName});
    return Session.fromJson(r.data);
  }

  Future<SessionDetail> getSession(String id) async {
    final r = await _dio.get('/api/sessions/$id');
    return SessionDetail.fromJson(r.data);
  }

  Future<void> deleteSession(String id) async {
    await _dio.delete('/api/sessions/$id');
  }

  // ----- Analysis ------------------------------------------------------- //
  Future<AnalysisResult> analyze({
    required String sessionId,
    required Uint8List bytes,
    required String filename,
    String note = '',
  }) async {
    final form = FormData.fromMap({
      'file': MultipartFile.fromBytes(bytes, filename: filename),
      'note': note,
    });
    final r = await _dio.post('/api/sessions/$sessionId/analyze', data: form);
    return AnalysisResult.fromJson(r.data);
  }

  Stream<SseEvent> summaryStream(String sessionId) => sseStream(
        url: '${ApiConfig.baseUrl}/api/sessions/$sessionId/analyze/summary',
      );

  // ----- Chat ----------------------------------------------------------- //
  Stream<SseEvent> messageStream(String sessionId, String text) => sseStream(
        method: 'POST',
        url: '${ApiConfig.baseUrl}/api/sessions/$sessionId/messages',
        headers: {'Content-Type': 'application/json'},
        body: {'text': text},
      );

  // ----- Medicines ------------------------------------------------------ //
  Future<List<Medicine>> listMedicines(String sessionId) async {
    final r = await _dio.get('/api/sessions/$sessionId/medicines');
    return (r.data as List).map((e) => Medicine.fromJson(e)).toList();
  }

  Future<Medicine> addMedicine(String sessionId, Medicine m) async {
    final r = await _dio.post('/api/sessions/$sessionId/medicines', data: m.toCreateJson());
    return Medicine.fromJson(r.data);
  }

  Future<Medicine> updateMedicine(String sessionId, String entryId, Medicine m) async {
    final r = await _dio.put('/api/sessions/$sessionId/medicines/$entryId', data: m.toCreateJson());
    return Medicine.fromJson(r.data);
  }

  Future<void> deleteMedicine(String sessionId, String entryId) async {
    await _dio.delete('/api/sessions/$sessionId/medicines/$entryId');
  }

  // ----- URL builders --------------------------------------------------- //
  String mediaUrl(String path) => '${ApiConfig.baseUrl}$path';
  String cameraWsUrl(String sessionId) =>
      '${ApiConfig.wsBaseUrl}/ws/sessions/$sessionId/camera';
}
