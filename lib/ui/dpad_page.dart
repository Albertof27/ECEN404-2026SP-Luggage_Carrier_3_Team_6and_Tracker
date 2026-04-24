import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/ble_controller_provider.dart';
import '../state/manual_mode_provider.dart';

class DPadPage extends ConsumerStatefulWidget {
  const DPadPage({Key? key}) : super(key: key);

  @override
  ConsumerState<DPadPage> createState() => _DPadPageState();
}

class _DPadPageState extends ConsumerState<DPadPage> {


  // Helper widget to build the directional buttons
  Widget _buildDirectionButton(IconData icon, String command) {
    final isManualModeOn = ref.watch(manualModeProvider);
    return GestureDetector(
      onTapDown: (_) {
        if (isManualModeOn) {
          ref.read(bleControllerProvider).sendMoveCommand(command);
        }
      },
      onTapUp: (_) {
        if (isManualModeOn) {
          ref.read(bleControllerProvider).sendMoveCommand('S');
        }
      },
      onTapCancel: () {
        if (isManualModeOn) {
          ref.read(bleControllerProvider).sendMoveCommand('S');
        }
      },
      child: Opacity(
        opacity: isManualModeOn ? 1.0 : 0.3,
        child: Container(
          width: 80,
          height: 80,
          decoration: BoxDecoration(
            color: Colors.blueGrey.shade800,
            shape: BoxShape.circle,
            boxShadow: isManualModeOn
                ? [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.3),
                      blurRadius: 10,
                      offset: const Offset(0, 5),
                    )
                  ]
                : [],
          ),
          child: Icon(icon, size: 48, color: Colors.white),
        ),
      ),
    );
  }

  // --- NEW: BIG TOGGLE BUTTON ---
  Widget _buildModeToggleButton() {
    final isManualModeOn = ref.watch(manualModeProvider);
    return GestureDetector(
      onTap: () {
        // TOGGLE THE PROVIDER STATE (not local setState)
        ref.read(manualModeProvider.notifier).state = !isManualModeOn;
        
        String cmd = !isManualModeOn ? "T:1" : "T:0";
        ref.read(bleControllerProvider).sendMoveCommand(cmd);
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 25, horizontal: 20),
        margin: const EdgeInsets.symmetric(horizontal: 20),
        decoration: BoxDecoration(
          color: isManualModeOn ? Colors.green.shade600 : Colors.red.shade600,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: isManualModeOn
                  ? Colors.green.withOpacity(0.4)
                  : Colors.red.withOpacity(0.4),
              blurRadius: 15,
              offset: const Offset(0, 8),
            ),
          ],
          border: Border.all(
            color: isManualModeOn ? Colors.green.shade800 : Colors.red.shade800,
            width: 3,
          ),
        ),
        child: Column(
          children: [
            // Icon at the top
            Icon(
              isManualModeOn ? Icons.check_circle : Icons.warning_rounded,
              size: 50,
              color: Colors.white,
            ),
            const SizedBox(height: 10),
            // Main text
            Text(
              isManualModeOn ? "IN MANUAL MODE" : "STOP ROVER",
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
                color: Colors.white,
                letterSpacing: 1.2,
              ),
            ),
            const SizedBox(height: 5),
            // Subtitle text
            Text(
              isManualModeOn
                  ? "You have full control"
                  : "Tap to go into manual mode",
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 16,
                color: Colors.white.withOpacity(0.9),
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isManualModeOn = ref.watch(manualModeProvider);
    final currentSpeed = ref.watch(speedProvider);
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
      body: SingleChildScrollView(
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const SizedBox(height: 30),

              // --- BIG RED/GREEN TOGGLE BUTTON ---
              _buildModeToggleButton(),

              const SizedBox(height: 30),

              // // --- SPEED SLIDER PANEL ---
              // Padding(
              //   padding: const EdgeInsets.symmetric(horizontal: 30.0),
              //   child: Container(
              //     padding: const EdgeInsets.all(16),
              //     decoration: BoxDecoration(
              //       color: Colors.white,
              //       borderRadius: BorderRadius.circular(15),
              //       boxShadow: [
              //         BoxShadow(
              //           color: Colors.black.withOpacity(0.1),
              //           blurRadius: 10,
              //           offset: const Offset(0, 4),
              //         ),
              //       ],
              //     ),
              //     child: Column(
              //       children: [
              //         Text(
              //           "Speed: ${currentSpeed.toInt()}%",
              //           style: const TextStyle(
              //               fontWeight: FontWeight.bold, fontSize: 16),
              //         ),
              //         Slider(
              //           value: currentSpeed,
              //           min: 0,
              //           max: 100,
              //           divisions: 100,
              //           activeColor: Colors.blueGrey.shade900,
              //           onChanged: isManualModeOn
              //               ? (double value) {
              //                   ref.read(speedProvider.notifier).state = value;
              //                 }
              //               : null,
              //           onChangeEnd: (double finalValue) {
              //             ref
              //                 .read(bleControllerProvider)
              //                 .sendMoveCommand("V:${finalValue.toInt()}");
              //           },
              //         ),
              //       ],
              //     ),
              //   ),
              // ),
              const SizedBox(height: 40),

              // --- D-PAD ---
              _buildDirectionButton(
                  Icons.keyboard_double_arrow_up_rounded, 'F'),
              const SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _buildDirectionButton(
                      Icons.keyboard_double_arrow_left_rounded, 'L'),
                  const SizedBox(width: 80),
                  _buildDirectionButton(
                      Icons.keyboard_double_arrow_right_rounded, 'R'),
                ],
              ),
              const SizedBox(height: 20),
              _buildDirectionButton(
                  Icons.keyboard_double_arrow_down_rounded, 'B'),
              const SizedBox(height: 30),
            ],
          ),
        ),
      ),
    );
  }
}

