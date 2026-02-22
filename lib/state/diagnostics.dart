import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'ble_state.dart';

/// Runs a live "demo" in the real app:
/// - shows normal weight -> overweight -> back under
/// - shows in range -> out of range -> back in range
///
/// Call this from a button in your UI.
Future<void> runBleSelfTest(WidgetRef ref) async {
  // 1) Start in a normal state
  ref.read(weightThresholdProvider.notifier).state = 20.0;
  ref.read(weightProvider.notifier).state = 10.0;
  ref.read(rssiProvider.notifier).state = -60; // strong signal, close

  // Let UI settle
  await Future.delayed(const Duration(seconds: 1));

  // 2) Go overweight (user should see overload color / icon)
  ref.read(weightProvider.notifier).state = 25.0;
  await Future.delayed(const Duration(seconds: 2));

  // 3) Back under limit
  ref.read(weightProvider.notifier).state = 15.0;
  await Future.delayed(const Duration(seconds: 2));

  // 4) Simulate going out of range (weak RSSI -> big distance)
  ref.read(rssiProvider.notifier).state = -80;
  await Future.delayed(const Duration(seconds: 2));

  // 5) Back in range
  ref.read(rssiProvider.notifier).state = -60;
  await Future.delayed(const Duration(seconds: 1));

  // Optional: restore "normal" defaults
  ref.read(weightProvider.notifier).state = 0.0;
  ref.read(rssiProvider.notifier).state = null;
}
