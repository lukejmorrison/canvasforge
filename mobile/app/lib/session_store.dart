import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'pairing.dart';

const sessionStorageKey = 'canvasforge-mobile-pair';

class SessionStore {
  SessionStore({this._preferences});

  SharedPreferences? _preferences;

  Future<SharedPreferences> _prefs() async {
    return _preferences ??= await SharedPreferences.getInstance();
  }

  Future<PairSession?> load() async {
    final raw = (await _prefs()).getString(sessionStorageKey);
    if (raw == null || raw.isEmpty) {
      return null;
    }
    final decoded = jsonDecode(raw);
    if (decoded is! Map<String, dynamic>) {
      return null;
    }
    final session = PairSession.fromJson(decoded);
    return session.isValid ? session : null;
  }

  Future<void> save(PairSession session) async {
    await (await _prefs()).setString(sessionStorageKey, jsonEncode(session.toJson()));
  }

  Future<void> clear() async {
    await (await _prefs()).remove(sessionStorageKey);
  }
}
