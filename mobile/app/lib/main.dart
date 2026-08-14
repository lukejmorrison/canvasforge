import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import 'pairing.dart';
import 'session_store.dart';
import 'sync_client.dart';

const _gold = Color(0xFFF6C21A);
const _bg = Color(0xFF12141A);
const _card = Color(0xFF1C212B);

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(CanvasForgeApp());
}

class CanvasForgeApp extends StatelessWidget {
  CanvasForgeApp({
    super.key,
    SyncClient? client,
    SessionStore? store,
    ImagePicker? picker,
    this.initialSession,
  })  : client = client ?? SyncClient(phoneName: _defaultPhoneName()),
        store = store ?? SessionStore(),
        picker = picker ?? ImagePicker();

  final SyncClient client;
  final SessionStore store;
  final ImagePicker picker;
  final PairSession? initialSession;

  static String _defaultPhoneName() {
    try {
      return Platform.operatingSystem;
    } on UnsupportedError {
      return 'CanvasForge phone';
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CanvasForge',
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: _bg,
        colorScheme: const ColorScheme.dark(
          primary: _gold,
          secondary: _gold,
          surface: _card,
        ),
        useMaterial3: true,
      ),
      home: HomePage(
        client: client,
        store: store,
        picker: picker,
        initialSession: initialSession,
      ),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({
    super.key,
    required this.client,
    required this.store,
    required this.picker,
    this.initialSession,
  });

  final SyncClient client;
  final SessionStore store;
  final ImagePicker picker;
  final PairSession? initialSession;

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final _codeController = TextEditingController();
  PairSession? _session;
  PairingLink? _pending;
  String _securityCode = '';
  String _status = '';
  bool _busy = false;
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    final stored = widget.initialSession ?? await widget.store.load();
    if (!mounted) {
      return;
    }
    setState(() {
      _session = stored;
      _ready = true;
    });
  }

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _beginFromCode(String raw) async {
    setState(() {
      _busy = true;
      _status = '';
    });
    try {
      final link = PairingLink.parse(raw);
      final offer = await widget.client.fetchOffer(link);
      if (!mounted) {
        return;
      }
      setState(() {
        _pending = link;
        _securityCode = offer.securityCode;
        _status = 'Check the same code on the desktop, then confirm both sides.';
      });
    } on FormatException catch (err) {
      setState(() => _status = err.message);
    } on SyncException catch (err) {
      setState(() => _status = err.message);
    } catch (err) {
      setState(() => _status = 'Could not reach the desktop. $err');
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  Future<void> _confirmPair() async {
    final link = _pending;
    if (link == null) {
      return;
    }
    setState(() {
      _busy = true;
      _status = 'Confirming…';
    });
    try {
      final status = await widget.client.confirmPhone(link);
      if (status.isPaired) {
        await _finishPair(PairSession(baseUrl: link.baseUrl, deviceToken: status.deviceToken!));
        return;
      }
      setState(() => _status = 'Waiting for the desktop to confirm the same security code…');
      final session = await widget.client.waitUntilPaired(link);
      await _finishPair(session);
    } on SyncException catch (err) {
      setState(() => _status = err.message);
    } catch (err) {
      setState(() => _status = 'Pairing failed. $err');
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  Future<void> _finishPair(PairSession session) async {
    await widget.store.save(session);
    if (!mounted) {
      return;
    }
    setState(() {
      _session = session;
      _pending = null;
      _securityCode = '';
      _status = 'Paired. This phone can send grabs without scanning again.';
    });
  }

  Future<void> _scanQr() async {
    final code = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const QrScanPage()),
    );
    if (code == null || code.isEmpty) {
      return;
    }
    _codeController.text = code;
    await _beginFromCode(code);
  }

  Future<void> _sendGrab(ImageSource source) async {
    final session = _session;
    if (session == null) {
      return;
    }
    final file = await widget.picker.pickImage(source: source);
    if (file == null) {
      return;
    }
    setState(() {
      _busy = true;
      _status = 'Sending ${file.name}…';
    });
    try {
      final bytes = Uint8List.fromList(await file.readAsBytes());
      final result = await widget.client.uploadGrab(
        session,
        bytes,
        contentType: file.mimeType ?? 'application/octet-stream',
        filename: file.name,
      );
      if (!mounted) {
        return;
      }
      setState(() => _status = 'Saved on desktop as ${result.name}');
    } on SyncException catch (err) {
      setState(() => _status = err.message);
    } catch (err) {
      setState(() => _status = 'Upload failed. $err');
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  Future<void> _unpair() async {
    await widget.store.clear();
    if (!mounted) {
      return;
    }
    setState(() {
      _session = null;
      _pending = null;
      _securityCode = '';
      _status = 'This phone forgot the desktop. Pair again from Settings → Mobile.';
    });
  }

  @override
  Widget build(BuildContext context) {
    if (!_ready) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const _Header(),
            const SizedBox(height: 20),
            if (_session == null) _pairCard() else _captureCard(),
          ],
        ),
      ),
    );
  }

  Widget _pairCard() {
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Pair with desktop', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          const Text(
            'On the desktop open Settings → Mobile → Pair Mobile Device. '
            'Scan the QR code, or paste the pairing code.',
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _busy ? null : _scanQr,
            icon: const Icon(Icons.qr_code_scanner),
            label: const Text('Scan desktop QR code'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _codeController,
            enabled: !_busy,
            decoration: const InputDecoration(
              labelText: 'Pairing code',
              hintText: '192.168.1.10:17831#token',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: _busy ? null : () => _beginFromCode(_codeController.text),
            child: const Text('Use pairing code'),
          ),
          if (_securityCode.isNotEmpty) ...[
            const SizedBox(height: 20),
            const Text('Confirm this security code matches the desktop:'),
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(
                _securityCode,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 2,
                  color: _gold,
                ),
              ),
            ),
            FilledButton(
              onPressed: _busy ? null : _confirmPair,
              child: const Text('Confirm pairing'),
            ),
          ],
          if (_status.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(_status),
          ],
        ],
      ),
    );
  }

  Widget _captureCard() {
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Send a screen grab', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          const Text(
            'Grabs land in the same Image Library folder the desktop already watches. '
            'Then use Send to Agent on the desktop.',
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _busy ? null : () => _sendGrab(ImageSource.gallery),
            icon: const Icon(Icons.photo_library_outlined),
            label: const Text('Choose photo or screenshot'),
          ),
          const SizedBox(height: 12),
          FilledButton.tonalIcon(
            onPressed: _busy ? null : () => _sendGrab(ImageSource.camera),
            icon: const Icon(Icons.photo_camera_outlined),
            label: const Text('Take photo'),
          ),
          if (_status.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(_status),
          ],
          TextButton(
            onPressed: _busy ? null : _unpair,
            child: const Text('Forget this desktop'),
          ),
        ],
      ),
    );
  }
}

class QrScanPage extends StatelessWidget {
  const QrScanPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan pairing QR')),
      body: MobileScanner(
        onDetect: (capture) {
          for (final barcode in capture.barcodes) {
            final value = barcode.rawValue;
            if (value != null && value.isNotEmpty) {
              Navigator.of(context).pop(value);
              return;
            }
          }
        },
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header();

  @override
  Widget build(BuildContext context) {
    return const Row(
      children: [
        Icon(Icons.auto_awesome, color: _gold, size: 36),
        SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('CanvasForge', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
              Text('Capture companion — sends grabs to your desktop library'),
            ],
          ),
        ),
      ],
    );
  }
}

class _Card extends StatelessWidget {
  const _Card({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF2A3140)),
      ),
      child: Padding(padding: const EdgeInsets.all(16), child: child),
    );
  }
}
