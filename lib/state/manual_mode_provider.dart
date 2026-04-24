import 'package:flutter_riverpod/flutter_riverpod.dart';

// This provider keeps track of manual mode state across the app
final manualModeProvider = StateProvider<bool>((ref) => false);

// This provider keeps track of the speed setting
final speedProvider = StateProvider<double>((ref) => 50.0);