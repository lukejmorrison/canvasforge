import 'dart:convert';
import 'dart:typed_data';

import 'package:canvasforge_mobile/pairing.dart';
import 'package:canvasforge_mobile/sync_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const link = PairingLink(
    baseUrl: 'http://192.168.1.20:17831',
    token: 'pair-token',
    host: '192.168.1.20',
    port: '17831',
  );

  test('fetchOffer reads the desktop security code', () async {
    final client = SyncClient(
      phoneName: 'Pixel',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/pair/offer');
        expect(request.url.queryParameters['token'], 'pair-token');
        return http.Response(
          jsonEncode({
            'state': 'waiting',
            'security_code': 'AEAD-7VEH',
            'name': 'Omarchy',
          }),
          200,
        );
      }),
    );
    final offer = await client.fetchOffer(link);
    expect(offer.securityCode, 'AEAD-7VEH');
    expect(offer.name, 'Omarchy');
  });

  test('confirmPhone then uploadGrab uses the device token', () async {
    var confirmCalls = 0;
    var uploadCalls = 0;
    final client = SyncClient(
      phoneName: 'iPhone',
      httpClient: MockClient((request) async {
        if (request.url.path == '/api/pair/confirm') {
          confirmCalls += 1;
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          expect(body['token'], 'pair-token');
          expect(body['name'], 'iPhone');
          return http.Response(
            jsonEncode({
              'state': 'paired',
              'device_token': 'device-secret',
              'security_code': 'AEAD-7VEH',
            }),
            200,
          );
        }
        if (request.url.path == '/api/upload') {
          uploadCalls += 1;
          expect(request.headers['authorization'], 'Bearer device-secret');
          expect(request.headers['x-filename'], 'phone-grab.png');
          return http.Response(
            jsonEncode({
              'ok': true,
              'name': 'phone-grab.png',
              'path': '/tmp/Screenshots/phone-grab.png',
            }),
            200,
          );
        }
        return http.Response('{"error":"unexpected"}', 404);
      }),
    );

    final status = await client.confirmPhone(link);
    expect(status.isPaired, isTrue);
    final result = await client.uploadGrab(
      PairSession(baseUrl: link.baseUrl, deviceToken: status.deviceToken!),
      Uint8List.fromList(const [0x89, 0x50, 0x4E, 0x47]),
      filename: 'phone-grab.png',
    );
    expect(result.name, 'phone-grab.png');
    expect(confirmCalls, 1);
    expect(uploadCalls, 1);
  });

  test('uploadGrab rejects an unpaired token', () async {
    final client = SyncClient(
      httpClient: MockClient((request) async {
        return http.Response(jsonEncode({'error': 'Phone is not paired'}), 403);
      }),
    );
    expect(
      () => client.uploadGrab(
        const PairSession(baseUrl: 'http://127.0.0.1:17831', deviceToken: 'nope'),
        Uint8List.fromList(const [1, 2, 3]),
      ),
      throwsA(isA<SyncException>()),
    );
  });
}
