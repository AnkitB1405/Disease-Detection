import 'package:flutter/foundation.dart';

/// Backend connection settings.
///
/// Defaults are chosen so the app "just works" against a backend started with
/// `python server.py` on the same machine:
///   * Web / Windows / desktop -> localhost
///   * Android emulator        -> 10.0.2.2 (the emulator's alias for the host)
///
/// For a physical phone on the same Wi-Fi, pass the host machine's LAN IP:
///   flutter run --dart-define=API_HOST=192.168.1.50 --dart-define=API_PORT=8000
class ApiConfig {
  static const String _hostDefine =
      String.fromEnvironment('API_HOST', defaultValue: '');
  static const String _portDefine =
      String.fromEnvironment('API_PORT', defaultValue: '8000');

  static String get host {
    if (_hostDefine.isNotEmpty) return _hostDefine;
    if (kIsWeb) return 'localhost';
    // Android emulator maps the host loopback to 10.0.2.2.
    if (defaultTargetPlatform == TargetPlatform.android) return '10.0.2.2';
    // Use IPv4 explicitly on desktop: "localhost" can resolve to IPv6 (::1)
    // first on Windows, which the IPv4 uvicorn server does not listen on.
    return '127.0.0.1';
  }

  static String get port => _portDefine;
  static String get baseUrl => 'http://$host:$port';
  static String get wsBaseUrl => 'ws://$host:$port';
}
