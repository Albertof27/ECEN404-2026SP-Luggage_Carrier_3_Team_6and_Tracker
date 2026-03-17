import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/ble_controller_provider.dart';

class DPadPage extends ConsumerWidget {
  const DPadPage({Key? key}) : super(key: key);

  // Helper widget to build the directional buttons
  Widget _buildDirectionButton(WidgetRef ref, IconData icon, String command) {
    return GestureDetector(
      // 1. User presses down -> Send the movement command (F, B, L, or R)
      onTapDown: (_) {
        // NOTE: Replace `bleControllerProvider` with the actual name of your provider!
        ref.read(bleControllerProvider).sendMoveCommand(command);
      },
      // 2. User releases finger -> Send the Stop command ('S')
      onTapUp: (_) {
        ref.read(bleControllerProvider).sendMoveCommand('S');
      },
      // 3. User drags finger off the button -> Send the Stop command ('S')
      onTapCancel: () {
        ref.read(bleControllerProvider).sendMoveCommand('S');
      },
      child: Container(
        width: 80,
        height: 80,
        decoration: BoxDecoration(
          color: Colors.blueGrey.shade800, // Nice dark tech-looking button
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.3),
              blurRadius: 10,
              offset: const Offset(0, 5),
            ),
          ],
        ),
        child: Icon(icon, size: 48, color: Colors.white),
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Optional: Watch your connection state provider to disable buttons if disconnected
    // final connState = ref.watch(connectionStateProvider);

    return Scaffold(
      backgroundColor: Colors.grey.shade100,
      appBar: AppBar(
        title: const Text(
          "Rover Control",
          style: TextStyle(color: Colors.white),
        ),
        backgroundColor: Colors.blueGrey.shade900,
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // FORWARD BUTTON
            _buildDirectionButton(ref, Icons.keyboard_double_arrow_up_rounded, 'F'),
            const SizedBox(height: 20),
            
            // LEFT & RIGHT BUTTONS
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _buildDirectionButton(ref, Icons.keyboard_double_arrow_left_rounded, 'L'),
                const SizedBox(width: 80), // Empty space in the center of the D-Pad
                _buildDirectionButton(ref, Icons.keyboard_double_arrow_right_rounded, 'R'),
              ],
            ),
            const SizedBox(height: 20),
            
            // BACKWARD BUTTON
            _buildDirectionButton(ref, Icons.keyboard_double_arrow_down_rounded, 'B'),
          ],
        ),
      ),
    );
  }
}