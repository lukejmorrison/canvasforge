import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import 'pairing.dart';

/// LAN/Tailscale client for `/api/pair/*` and `/api/upload`.
class SyncClient {
  SyncClient({http.Client? httpClient, this.phoneName = 'CanvasForge phone'})
      : _http = httpClient ?? http.Client();

  final http.Client _http;
  final String phoneName;

  Future<PairOffer> fetchOffer(PairingLink link) async {
    final uri = Uri.parse('${link.baseUrl}/api/pair/offer').replace(
      queryParameters: {'token': link.token},
    );
    final response = await _http.get(uri);
    final body = _decode(response);
    if (response.statusCode != 200) {
      throw SyncException(body['error'] as String? ?? 'Desktop is not waiting to pair');
    }
    return PairOffer.fromJson(body);
  }

  Future<PairStatus> confirmPhone(PairingLink link) async {
    final uri = Uri.parse('${link.baseUrl}/api/pair/confirm');
    final response = await _http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'token': link.token, 'name': phoneName}),
    );
    final body = _decode(response);
    if (response.statusCode != 200) {
      throw SyncException(body['error'] as String? ?? 'Could not confirm pairing');
    }
    return PairStatus.fromJson(body);
  }

  Future<PairStatus> pairingStatus(PairingLink link) async {
    final uri = Uri.parse('${link.baseUrl}/api/pair/status').replace(
      queryParameters: {'token': link.token},
    );
    final response = await _http.get(uri);
    final body = _decode(response);
    if (response.statusCode != 200) {
      throw SyncException(body['error'] as String? ?? 'Could not read pairing status');
    }
    return PairStatus.fromJson(body);
  }

  Future<PairSession> waitUntilPaired(PairingLink link, {int attempts = 60}) async {
    for (var i = 0; i < attempts; i++) {
      final status = await pairingStatus(link);
      if (status.isPaired) {
        return PairSession(baseUrl: link.baseUrl, deviceToken: status.deviceToken!);
      }
      await Future<void>.delayed(const Duration(seconds: 1));
    }
    throw const SyncException('Still waiting for the desktop to confirm.');
  }

  Future<UploadResult> uploadGrab(
    PairSession session,
    Uint8List bytes, {
    String contentType = 'image/png',
    String filename = 'mobile-grab.png',
  }) async {
    if (bytes.isEmpty) {
      throw const SyncException('Grab is empty');
    }
    final uri = Uri.parse('${session.baseUrl}/api/upload');
    final response = await _http.post(
      uri,
      headers: {
        'Authorization': 'Bearer ${session.deviceToken}',
        'Content-Type': contentType,
        'X-Filename': filename,
      },
      body: bytes,
    );
    final body = _decode(response);
    if (response.statusCode != 200) {
      throw SyncException(body['error'] as String? ?? 'Upload failed');
    }
    return UploadResult.fromJson(body);
  }

  Map<String, dynamic> _decode(http.Response response) {
    if (response.body.isEmpty) {
      return <String, dynamic>{};
    }
    final decoded = jsonDecode(response.body);
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }
    return <String, dynamic>{};
  }
}

class SyncException implements Exception {
  const SyncException(this.message);

  final String message;

  @override
  String toString() => message;
}
