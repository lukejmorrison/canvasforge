import 'package:canvasforge_mobile/main.dart';
import 'package:canvasforge_mobile/pairing.dart';
import 'package:canvasforge_mobile/session_store.dart';
import 'package:canvasforge_mobile/sync_client.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('pair screen asks to scan the desktop QR', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(
      CanvasForgeApp(
        store: SessionStore(),
        client: SyncClient(httpClient: MockClient((request) async => http.Response('{}', 404))),
        initialSession: null,
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Pair with desktop'), findsOneWidget);
    expect(find.text('Scan desktop QR code'), findsOneWidget);
    expect(find.text('Use pairing code'), findsOneWidget);
  });

  testWidgets('paired session shows the capture actions', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(
      CanvasForgeApp(
        store: SessionStore(),
        client: SyncClient(httpClient: MockClient((request) async => http.Response('{}', 404))),
        initialSession: const PairSession(
          baseUrl: 'http://192.168.1.20:17831',
          deviceToken: 'device-secret',
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Send a screen grab'), findsOneWidget);
    expect(find.text('Choose photo or screenshot'), findsOneWidget);
    expect(find.text('Take photo'), findsOneWidget);
    expect(find.byIcon(Icons.add), findsNothing);
  });
}
