/// Pairing-link helpers shared by iOS and Android.
///
/// Matches the desktop protocol in `mobile_sync.parse_pairing_link`:
/// a scanned QR URL (`http://host:port/?pair=TOKEN`) or a pasted
/// `host:port#TOKEN` code.
class PairingLink {
  const PairingLink({
    required this.baseUrl,
    required this.token,
    required this.host,
    required this.port,
  });

  final String baseUrl;
  final String token;
  final String host;
  final String port;

  static const int defaultPort = 17831;

  static PairingLink parse(String raw) {
    final text = raw.trim();
    if (text.isEmpty) {
      throw const FormatException('Pairing code is empty');
    }
    if (text.startsWith('http://') || text.startsWith('https://')) {
      final uri = Uri.parse(text);
      final token = uri.queryParameters['pair'] ?? '';
      if (token.isEmpty) {
        throw const FormatException('Pairing link is missing the pair token');
      }
      final port = uri.hasPort ? '${uri.port}' : '';
      return PairingLink(
        baseUrl: '${uri.scheme}://${uri.authority}',
        token: token,
        host: uri.host,
        port: port,
      );
    }
    if (text.contains('#')) {
      final hash = text.indexOf('#');
      final hostport = text.substring(0, hash).trim();
      final token = text.substring(hash + 1).trim();
      if (token.isEmpty) {
        throw const FormatException('Pairing code is missing the pair token');
      }
      String host;
      String port;
      if (hostport.contains(':')) {
        final split = hostport.lastIndexOf(':');
        host = hostport.substring(0, split);
        port = hostport.substring(split + 1);
      } else {
        host = hostport;
        port = '$defaultPort';
      }
      return PairingLink(
        baseUrl: 'http://$host:$port',
        token: token,
        host: host,
        port: port,
      );
    }
    throw const FormatException('Use the QR link or host:port#token');
  }
}

class PairOffer {
  const PairOffer({
    required this.state,
    required this.securityCode,
    this.name = 'CanvasForge',
  });

  final String state;
  final String securityCode;
  final String name;

  factory PairOffer.fromJson(Map<String, dynamic> json) {
    return PairOffer(
      state: json['state'] as String? ?? 'waiting',
      securityCode: json['security_code'] as String? ?? '',
      name: json['name'] as String? ?? 'CanvasForge',
    );
  }
}

class PairStatus {
  const PairStatus({
    required this.state,
    this.deviceToken,
    this.securityCode,
  });

  final String state;
  final String? deviceToken;
  final String? securityCode;

  bool get isPaired => state == 'paired' && deviceToken != null && deviceToken!.isNotEmpty;

  factory PairStatus.fromJson(Map<String, dynamic> json) {
    return PairStatus(
      state: json['state'] as String? ?? 'idle',
      deviceToken: json['device_token'] as String?,
      securityCode: json['security_code'] as String?,
    );
  }
}

class PairSession {
  const PairSession({required this.baseUrl, required this.deviceToken});

  final String baseUrl;
  final String deviceToken;

  Map<String, String> toJson() => {
        'base': baseUrl,
        'device_token': deviceToken,
      };

  factory PairSession.fromJson(Map<String, dynamic> json) {
    return PairSession(
      baseUrl: json['base'] as String? ?? '',
      deviceToken: json['device_token'] as String? ?? '',
    );
  }

  bool get isValid => baseUrl.isNotEmpty && deviceToken.isNotEmpty;
}

class UploadResult {
  const UploadResult({required this.name, required this.path});

  final String name;
  final String path;

  factory UploadResult.fromJson(Map<String, dynamic> json) {
    return UploadResult(
      name: json['name'] as String? ?? '',
      path: json['path'] as String? ?? '',
    );
  }
}
