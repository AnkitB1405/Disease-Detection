import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

/// One Server-Sent Event from the backend: {"type": ..., "content": ...}.
class SseEvent {
  final String type; // token | question | done | error
  final String content;
  const SseEvent(this.type, this.content);
}

/// Open an SSE connection (GET or POST) and yield parsed events.
///
/// The backend streams `data: {json}\n\n` frames. Works for both the Phase-2
/// summary (GET) and the chat endpoint (POST with a JSON body).
Stream<SseEvent> sseStream({
  required String url,
  String method = 'GET',
  Map<String, String>? headers,
  Object? body,
}) async* {
  final client = http.Client();
  try {
    final request = http.Request(method, Uri.parse(url));
    request.headers['Accept'] = 'text/event-stream';
    if (headers != null) request.headers.addAll(headers);
    if (body != null) {
      request.body = body is String ? body : jsonEncode(body);
    }

    final response = await client.send(request);
    if (response.statusCode >= 400) {
      yield SseEvent('error', 'Server returned ${response.statusCode}');
      return;
    }

    final lines =
        response.stream.transform(utf8.decoder).transform(const LineSplitter());
    await for (final line in lines) {
      if (!line.startsWith('data:')) continue;
      final data = line.substring(5).trim();
      if (data.isEmpty) continue;
      try {
        final map = jsonDecode(data) as Map<String, dynamic>;
        yield SseEvent(
          map['type'] as String? ?? 'token',
          map['content'] as String? ?? '',
        );
      } catch (_) {
        // Ignore malformed frames; keep the stream alive.
      }
    }
  } catch (e) {
    yield SseEvent('error', e.toString());
  } finally {
    client.close();
  }
}
