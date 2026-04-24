import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:math' as math;
//import 'package:riverpod/riverpod.dart';
//the state provider holds a string on whether or not the rover is connected to tell the user
final connectionStateProvider = StateProvider<String>((_) => 'disconnected');
//tells the user what the weight is
final weightProvider          = StateProvider<double>((_) => 0.0);
//this repreents events like if the rover is overwieght and stuff
final eventsBitsProvider      = StateProvider<int>((_) => 0);

  

// User/feature-configurable threshold (lbs). Default: 20 lb
final weightThresholdProvider = StateProvider<double>((_) => 20.0);

// True when current weight exceeds the threshold
final isOverloadedProvider = Provider<bool>((ref) {
  final w = ref.watch(weightProvider);
  final t = ref.watch(weightThresholdProvider);
  return w > t;
});

// Optional: formatted string for UI
final weightStringProvider = Provider<String>((ref) {
  final w = ref.watch(weightProvider);
  return '${w.toStringAsFixed(1)} lbs';
});


//  RSSI and Distance Estimation
// ==========================================================

/// Latest averaged RSSI reading in dBm.
/// Null until the first reading arrives.
final rssiProvider = StateProvider<int?>((_) => null);

/// Configuration constants for the path-loss model.
/// - [txPowerAt1m]: measured RSSI at 1 meter
/// - [pathLossExponent]: environment constant (≈2.0 indoors)
final rssiDistanceConfigProvider = Provider<RssiDistanceConfig>((_) =>
    const RssiDistanceConfig(txPowerAt1m: -59, pathLossExponent: 2.0));

/// Derived distance in meters using the log-distance path-loss model.
/// Returns null until we have a valid RSSI.
final distanceMetersProvider = Provider<double?>((ref) {
  final rssi = ref.watch(rssiProvider);
  if (rssi == null) return null;

  final cfg = ref.watch(rssiDistanceConfigProvider);
  return rssiToDistanceMeters(rssi.toDouble(), cfg);
});

/// True if rover appears to be more than 1.83 meters (≈6 ft) away.
final outOfRangeProvider = Provider<bool>((ref) {
  final d = ref.watch(distanceMetersProvider);
  return d != null && d > 1.83;
});

// ==========================================================
//  Helper Model + Function
// ==========================================================

/// Holds calibration constants for the distance formula.
class RssiDistanceConfig {
  /// RSSI measured at exactly 1 meter from the device.
  final double txPowerAt1m;

  /// Environment-dependent factor (≈1.6 open air, 2.0 indoors, 3+ cluttered)
  final double pathLossExponent;

  const RssiDistanceConfig({
    required this.txPowerAt1m,
    required this.pathLossExponent,
  });
}

/// Log-distance path loss model:
/// d = 10 ^ ((TxPower@1m - RSSI) / (10 * n))
double rssiToDistanceMeters(double rssi, RssiDistanceConfig cfg) {
  final exponent = (cfg.txPowerAt1m - rssi) / (10.0 * cfg.pathLossExponent);
  return math.exp(exponent * math.ln10);
}


