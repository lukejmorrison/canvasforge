import 'package:canvasforge_mobile/pairing.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('parses a scanned QR pairing URL', () {
    const raw = 'http://192.168.1.20:17831/?pair=deadbeefcafebabe0123456789abcdef';
    final link = PairingLink.parse(raw);
    expect(link.baseUrl, 'http://192.168.1.20:17831');
    expect(link.token, 'deadbeefcafebabe0123456789abcdef');
    expect(link.host, '192.168.1.20');
    expect(link.port, '17831');
  });

  test('parses a pasted host:port#token code', () {
    const raw = '192.168.1.20:17831#deadbeefcafebabe0123456789abcdef';
    final link = PairingLink.parse(raw);
    expect(link.baseUrl, 'http://192.168.1.20:17831');
    expect(link.token, 'deadbeefcafebabe0123456789abcdef');
    expect(link.port, '17831');
  });

  test('rejects an empty pairing code', () {
    expect(() => PairingLink.parse('   '), throwsA(isA<FormatException>()));
  });

  test('rejects a URL without a pair token', () {
    expect(
      () => PairingLink.parse('http://192.168.1.20:17831/'),
      throwsA(isA<FormatException>()),
    );
  });

  test('pair status is paired only with a device token', () {
    expect(const PairStatus(state: 'phone_confirmed').isPaired, isFalse);
    expect(
      const PairStatus(state: 'paired', deviceToken: 'abc').isPaired,
      isTrue,
    );
  });
}
