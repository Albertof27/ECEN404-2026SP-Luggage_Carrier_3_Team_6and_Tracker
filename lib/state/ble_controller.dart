import 'dart:async';
//brings in important librarries that allow you to subscribe to a ble event stream
import 'dart:typed_data';
//this allows you to decode notifications from the rover since they will be in bytes so it needs to be translated using things in this import
import 'package:permission_handler/permission_handler.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';
//this handles the read and write functions for the rover 

//this is just your bidge that you already made and the ble state that you made
import '../bridge/notify_bridge.dart';
import '../bridge/ble_bridge.dart';
import 'ble_state.dart';
import 'dart:math' as math;

/// === BLE UUIDs  ===
const String svcRover  = '3f09d95b-7f10-4c6a-8f0d-15a74be2b9b5';
const String chrWeight = 'a18f1f42-1f7d-4f62-9b9c-57e76a4c3140';
const String chrEvents = 'b3a1f6d4-37db-4e7c-a7ac-b3e74c3f8e6a';

const String chrLocation = 'e5b3c9f2-6d8e-4f1a-8c2d-2b9a1c3d4e5f';

const String chrMove = 'c7d8e9f0-1a2b-3c4d-5e6f-7a8b9c0d1e2f';

const String chrHeartbeat = 'd1e2f3a4-5b6c-7d8e-9f0a-1b2c3d4e5f6a';

/// Device name filter you expect in advertisements.
const String kTargetNameContains = 'Rover-01';
//const String kTargetNameContains = '';


/// Controller that listens to native BLE events and updates Riverpod state.
class BleController {
  // youre gonna use a ref to read/write the data from the ble
  BleController(this.ref) {
    //subscribes to the event stream that gives the phone messages like notifications from the rover and scan results
    _sub = BleBridge.events().listen(
      _onEvent,
      //if theres error this message will be sent
      onError: (Object err, StackTrace st) {
        ref.read(connectionStateProvider.notifier).state = 'error';
      },
      onDone: () {
        // Stream closed by native side, if i want to say something here imma leave it for future refrences
      },
      //if theres errors the stream wont close which is good because the stream can be a little flakey
      cancelOnError: false,
    );
  }
  //this store the riverpod ref because it's needed again
  final Ref ref;
  //this stops memeory leaks if the widget is disposed
  StreamSubscription? _sub;
  //stops multiple connect calls if many scan results arrive
  bool _connectingOrConnected = false;
  //scan time so there can be timeout so that you don't scan forever
  Timer? _scanTimer;


    // --- RSSI / distance helpers ---
  // Rolling window to smooth RSSI noise
  final List<int> _rssiWindow = <int>[];
  static const int _rssiWindowSize = 15;

  // Poll RSSI every second when connected
  Timer? _rssiPoll;

  //timer for heartbeat
  Timer? _heartbeatTimer;
  static const Duration _heartbeatInterval = Duration(milliseconds: 500);

  // Track last out-of-range status to avoid spamming notifications
  bool _wasOutOfRange = false;

  //weight tamper 
  double? _lastWeight;
  DateTime _lastWeightNotifyAt = DateTime.fromMillisecondsSinceEpoch(0);
  static const double _weightDeltaNotify = 1.0;
  static const Duration _minWeightNotifyInterval = Duration(seconds: 10);


  // ---------------- Public API ----------------


/// Sends a heartbeat signal to the Pi to indicate the app is still connected
Future<void> _sendHeartbeat() async {
  if (!_connectingOrConnected) return;
  
  try {
    // Send a simple byte (0x01) as the heartbeat signal
    // You can also use a timestamp or counter if needed
    final List<int> heartbeatData = [0x01];
    
    await BleBridge.write(
      svcRover,
      chrHeartbeat,
      heartbeatData,
      withResponse: false, // Use false for speed, heartbeats are frequent
    );
    // Uncomment for debugging:
     print("💓 [BLE] Heartbeat sent");
  } catch (e) {
    print("💔 [BLE] Heartbeat failed (will retry): $e");
    //await disconnect();
  }
}



///FAKEEEEEEEEEEEEE
Future<void> scanAndConnect() async {

  Map<Permission, PermissionStatus> statuses = await [
    Permission.bluetoothScan,
    Permission.bluetoothConnect,
    Permission.location,
    Permission.notification, // Request this early so it doesn't pop up later
  ].request();

  
if (statuses[Permission.bluetoothScan]?.isDenied ?? true) {
    ref.read(connectionStateProvider.notifier).state = 'perm-denied';
    return;
  }

  ref.read(connectionStateProvider.notifier).state = 'scanning';
  


  try {
    // 4. Start the scan (No redundant requestPermissions call here)
    await BleBridge.startScan(serviceUuids: []); 

    _scanTimer?.cancel();
    _scanTimer = Timer(const Duration(seconds: 15), () async {
      await BleBridge.stopScan();
      if (!_connectingOrConnected) {
        ref.read(connectionStateProvider.notifier).state = 'not-found';
      }
    });
  } catch (e) {
    print("📱 Scan Error: $e");
    ref.read(connectionStateProvider.notifier).state = 'scan-error';
  }

}





// THIS FUNCTION IS WHAT SENDS THE LOCATION TO THE PI


Future<void> sendLocation(double lat, double lon) async {
  if (!_connectingOrConnected) {
    print("📱 [BLE] Not connected. Can't send location.");
    return;
  }

  try {
    // 1. Create a byte buffer for two 32-bit floats
    final ByteData data = ByteData(8);
    data.setFloat32(0, lat, Endian.little);
    data.setFloat32(4, lon, Endian.little);

    // 2. Convert to List<int> for the MethodChannel
    final List<int> bytes = data.buffer.asUint8List().toList();

    // 3. Match your BleBridge.write positional parameters:
    // static Future<void> write(String svc, String chr, List<int> val, {bool withResponse=true})
    await BleBridge.write(
      svcRover,      // svc
      chrLocation,   // chr
      bytes,         // val
      withResponse: true,
    );

    print("📱 [BLE] Location sent: $lat, $lon");
  } catch (e) {
    print("📱 [BLE] Write Error: $e");
  }
}




Future<void> sendMoveCommand(String command) async {
  if (!_connectingOrConnected) {
    print("📱 [BLE] Not connected. Can't send move command.");
    return;
  }

  try {
    // Convert the string character (e.g., 'F') into a list of bytes
    final List<int> bytes = command.codeUnits;

    // Send it to the bridge
    await BleBridge.write(
      svcRover,      // Same service
      chrMove,       // New movement characteristic
      bytes,         // The encoded command
      withResponse: false, // 'false' is usually better for rapid movement commands to reduce latency
    );

    print("📱 [BLE] Move command sent: $command");
  } catch (e) {
    print("📱 [BLE] Move Command Error: $e");
  }
}






  //this kills the scan if its not scanning anything to free up resources
  Future<void> disconnect() async {
    print("🔌 [BLE] Disconnecting and cleaning up...");
    _scanTimer?.cancel();
    _heartbeatTimer?.cancel();
    _connectingOrConnected = false;

    ref.read(connectionStateProvider.notifier).state = 'disconnected'; 
    ref.read(rssiProvider.notifier).state = null;
    _wasOutOfRange = false;
    _rssiWindow.clear();
  
    await BleBridge.disconnect();
  }
  //this cancels the timer and the event subsrciption to prevent leaks
  void dispose() {
    _scanTimer?.cancel();
    _rssiPoll?.cancel();
    _heartbeatTimer?.cancel();
    _sub?.cancel();
  }
//--------------------------------------

//---------------------------------------
  // ---------------- Event handling ----------------
//this part decodes the event states from BLE to the actual app
  void _onEvent(dynamic e) {
    //this ensures theres always a map so it protects you from unexpected payloads
    if (e is! Map) return;
    final m = Map<String, dynamic>.from(e as Map);
    //handles other asynch events
    switch (m['type']) {
      case 'scanStarted':
        // i can put another message here to know that the scan started if i want to possibly update ui
        break;
      //this is for when a device was found and you check the name, if the name matches you stop scanning and conect the id to prevent multiple connects 





      case 'scanResult':
        final name = (m['name'] as String?) ?? '';
        final id = m['id'] as String?;

        print('📱 [BLE] Found device: name="$name", id="$id"');
        if (!_connectingOrConnected &&
            name.contains(kTargetNameContains)) {
          print('📱 [BLE] Matching device! Connecting to: $name');
          _connectingOrConnected = true;
          // Stop scanning and connect once.
          BleBridge.stopScan();

          () async {
            print('📱 [BLE] Waiting for hardware cooldown...');
            await Future.delayed(const Duration(milliseconds: 500));
          final id = m['id'] as String;
          print('📱 [BLE] Sending connect command to ID: $id');
          
          BleBridge.connect(id!);
          ref.read(connectionStateProvider.notifier).state = 'connecting';
          }();
        }
        break;





      //this function is when the connection state changed, so this will update the ui on whether the state is connected/disconnected and avoids 
      //enabling notify before the services exsist
      case 'connState':
        final state = (m['state'] as String?) ?? '';
        ref.read(connectionStateProvider.notifier).state = state;

        if (state == 'connected') {
          // We are definitively connected now.
          _connectingOrConnected = true;
          _scanTimer?.cancel();
          // Start periodic RSSI polling. Native code will answer with 'rssi' events.
          _rssiPoll?.cancel();
          _rssiPoll = Timer.periodic(const Duration(seconds: 1), (_) {
            BleBridge.readRssi(); // triggers Android onReadRemoteRssi -> {type:'rssi', value:int}
          });


    // ====================================
        
          
        
        } else {
          // Any non-connected state: reset flags, clear RSSI, stop polling.
          _connectingOrConnected = false;
          _rssiPoll?.cancel();
          _heartbeatTimer?.cancel();
          _rssiWindow.clear();
          ref.read(rssiProvider.notifier).state = null;
          _wasOutOfRange = false;
        }
        break;

      //now that the services are discovered you enable notifications from the rover
      case 'services':
        // Services are now discovered; safe to enable notifications.
        BleBridge.setNotify(svcRover, chrWeight, true);
        BleBridge.setNotify(svcRover, chrEvents, true);
        NotifyBridge.requestPermission();
        // ========== START HEARTBEAT HERE WITH DELAY ==========
        Future.delayed(const Duration(milliseconds: 500), () {
          if (_connectingOrConnected) {
            _heartbeatTimer?.cancel();
            _heartbeatTimer = Timer.periodic(_heartbeatInterval, (_) {
              _sendHeartbeat();
            });
            _sendHeartbeat();  // Send first heartbeat
            print('📱 [BLE] Heartbeat timer started after services discovered');
          }
        });
        // =====================================================
        break;
      
      //this is the part that actually extracts the info from the rover that will then later be decoded
      case 'notify': {
        final chr = (m['chr'] as String?) ?? '';
        final raw = (m['val'] as List?) ?? const [];
        final bytes = Uint8List.fromList(List<int>.from(raw));

        if (chr == chrWeight) {
          if (bytes.length >= 4) {
            final bd = ByteData.sublistView(bytes);
            final w = bd.getFloat32(0, Endian.little);
            ref.read(weightProvider.notifier).state = w;

            // --- Change detection + notification ---
            final prev = _lastWeight;
            _lastWeight = w;

            if (prev != null) {
              final now = DateTime.now();
              final since = now.difference(_lastWeightNotifyAt);

              final threshold = ref.read(weightThresholdProvider);
              final overloadedNow = w > threshold;
              final overloadedPrev = prev > threshold;

              final bigDelta = (w - prev).abs() >= _weightDeltaNotify;
              final crossedLimit = overloadedNow != overloadedPrev;

              if ((bigDelta || crossedLimit) && since >= _minWeightNotifyInterval) {
                _lastWeightNotifyAt = now;

                final body = crossedLimit
                    ? (overloadedNow
                        ? 'Overload: ${w.toStringAsFixed(1)} lb (limit ${threshold.toStringAsFixed(1)} lb)'
                        : 'Back under limit: ${w.toStringAsFixed(1)} lb (limit ${threshold.toStringAsFixed(1)} lb)')
                    : 'Weight changed to ${w.toStringAsFixed(1)} lb';

                NotifyBridge.showInstant(
                  title: 'Rover Weight Update',
                  body: body,
                );
              }
            }
          }
        } else if (chr == chrEvents) {
          if (bytes.length >= 2) {
            final bd = ByteData.sublistView(bytes);
            final bits = bd.getUint16(0, Endian.little);
            ref.read(eventsBitsProvider.notifier).state = bits;
          }
        }
        break;
      }

        

      case 'rssi': {
        // Expect: { type: 'rssi', value: int }
        final value = m['value'];
        if (value is! int) break;

        // Maintain a rolling window to average RSSI (stabilizes distance)
        _rssiWindow.add(value);
        if (_rssiWindow.length > _rssiWindowSize) _rssiWindow.removeAt(0);

        final avg = (_rssiWindow.reduce((a, b) => a + b) / _rssiWindow.length).round();
        ref.read(rssiProvider.notifier).state = avg;

        // Estimate distance using the log-distance path-loss model
        final cfg = ref.read(rssiDistanceConfigProvider);
        final distance = math.exp(((cfg.txPowerAt1m - avg) / (10.0 * cfg.pathLossExponent)) * math.ln10,);

        // Determine if we're beyond 6 ft (≈1.83 m)
        final outNow = distance > 1.83;

        // Edge-detect to avoid repeated alerts every second
        if (outNow != _wasOutOfRange) {
          _wasOutOfRange = outNow;
          if (outNow) {
           
            // BleBridge.showInstant('Rover out of range', '≈ ${distance.toStringAsFixed(1)} m');
          } else {
            //  "back in range" notification:
            // BleBridge.showInstant('Rover back in range', '≈ ${distance.toStringAsFixed(1)} m');
          }
        }
        break;
      }


      case 'scanError':
        // if scan fails theres surface code/message
        ref.read(connectionStateProvider.notifier).state = 'scan-error';
        break;
    }
  }
}
  