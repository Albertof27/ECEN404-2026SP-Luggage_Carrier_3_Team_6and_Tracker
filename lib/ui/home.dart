import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rover_app/state/ble_state.dart';
import 'package:rover_app/state/ble_controller_provider.dart' as providers;
import 'package:rover_app/ui/trip_logger_page.dart';
import 'package:rover_app/ui/profile_page.dart';
//import '../state/diagnostics.dart';
import '../state/auth_providers.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:rover_app/app_services.dart';
import 'package:rover_app/models/trip.dart';
import 'package:rover_app/ui/dpad_page.dart';
 



// Live list of this user's trips (most-recent first)
final tripsStreamProvider = StreamProvider<List<Trip>>((ref) async* {
  // Wait until AppServices has initialized a repo for the current user
  while (AppServices.I.currentUid == null) {
    await Future<void>.delayed(const Duration(milliseconds: 100));
  }

  // Now it's safe to access repo (initForUser has run)
  final repo = AppServices.I.repo;
  yield* repo.getTripsStream();
});

// Sum kilometers across this user's trips
final totalDistanceKmProvider = Provider<double>((ref) {
  final tripsAsync = ref.watch(tripsStreamProvider);
  final trips = tripsAsync.maybeWhen(data: (t) => t, orElse: () => const <Trip>[]);
  return trips.fold<double>(0.0, (sum, t) => sum + (t.distanceMeters / 1000.0));
});


class TripsDistanceChart extends StatelessWidget {
  final List<Trip> trips; // assumed most-recent first
  const TripsDistanceChart({super.key, required this.trips});

  @override
  Widget build(BuildContext context) {
    // Show at most last 10 trips to keep labels readable
    final data = (trips.length <= 10) ? trips : trips.sublist(0, 10);
    // reverse to show oldest (left) → newest (right)
    final bars = data.reversed.toList();

    final barGroups = List.generate(bars.length, (i) {
      final trip = bars[i];
      final km = (trip.distanceMeters / 1000.0);
      return BarChartGroupData(
        x: i,
        barRods: [
          BarChartRodData(toY: km, width: 18),
        ],
      );
    });

    String bottomLabel(int x) {
      final trip = bars[x];
      final name = trip.name.trim();
      if (name.isNotEmpty) {
        return (name.length <= 8) ? name : name.substring(0, 8);
      }
      final d = trip.startedAt.toLocal();
      return '${d.month}/${d.day}';
    }

    return BarChart(
      BarChartData(
        barGroups: barGroups,
        gridData: FlGridData(show: true),
        borderData: FlBorderData(show: false),
        titlesData: FlTitlesData(


        leftTitles: AxisTitles(
              sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 50,
              getTitlesWidget: (value, meta) {
                final maxY = meta.max;

                //  Hide the top-most label ONLY
                if ((value - maxY).abs() < 0.01) {
                  return const SizedBox.shrink();
                }

                // Normal labels for everything else
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Text(
                    value.toStringAsFixed(2),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                );
              },
            ),
          ),

          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                final x = value.toInt();
                if (x < 0 || x >= bars.length) return const SizedBox.shrink();
                return Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Transform.rotate(
                    angle: -1.2,  // approx -45 degrees
                    child: Text(
                      bottomLabel(x),
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),

                );
              },
            ),
          ),
          rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        ),
      ),
    );
  }
}




class RoverHome extends ConsumerWidget {
  
  const RoverHome({super.key});
/*
    Future<void> runBleSelfTest(WidgetRef ref) {
    return diag.runBleSelfTest(ref);
  }
  */
  

  @override
  Widget build(BuildContext context, WidgetRef ref) {


    final weight     = ref.watch(weightProvider);
    final weightStr  = ref.watch(weightStringProvider);
    final overloaded = ref.watch(isOverloadedProvider);
    final threshold  = ref.watch(weightThresholdProvider);

    final conn     = ref.watch(connectionStateProvider);
    final rssi     = ref.watch(rssiProvider);
    final distance = ref.watch(distanceMetersProvider);
    final outRange = ref.watch(outOfRangeProvider);
    final ble = ref.watch(providers.bleControllerProvider);

    Color statusColor() {
      if (conn == 'connected') {
        return outRange ? Colors.red : Colors.green;
      }
      if (conn == 'scanning' || conn == 'connecting') {
        return Colors.orange;
      }
      return Colors.grey;
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Rover Status'),
        actions: [






          IconButton(
            icon: const Icon(Icons.person),
            tooltip: 'Profile',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const ProfilePage()),
              );
            },
          ),

          IconButton(
            icon: const Icon(Icons.map_outlined),
            tooltip: 'Trip Logger',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const TripLoggerPage()),
              );
            },
          ),




          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Log out',
            onPressed: () async {
              await ref.read(authServiceProvider).signOut();
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Signed out')),
                );
              }
            },
          ),
        ],
      ),

            body: SingleChildScrollView(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              children: [
                // --- Your existing STATUS CARD (unchanged) ---
                Card(
                  elevation: 2,
                  margin: const EdgeInsets.all(16),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Connection pill
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          decoration: BoxDecoration(
                            color: statusColor().withOpacity(0.15),
                            borderRadius: BorderRadius.circular(999),
                            border: Border.all(color: statusColor(), width: 1),
                          ),
                          child: Text(
                            'Connection: $conn',
                            style: TextStyle(
                              color: statusColor(),
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),

                        // RSSI & Distance
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('RSSI', style: Theme.of(context).textTheme.bodyLarge),
                            Text(rssi == null ? '-- dBm' : '$rssi dBm'),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('Distance', style: Theme.of(context).textTheme.bodyLarge),
                            Text(distance == null ? '-- m' : '${distance.toStringAsFixed(2)} m'),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('6-ft Status', style: Theme.of(context).textTheme.bodyLarge),
                            Text(
                              outRange ? 'OUT OF RANGE' : 'OK',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: outRange ? Colors.red : Colors.green,
                              ),
                            ),
                          ],
                        ),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('Weight', style: Theme.of(context).textTheme.bodyLarge),
                            Text(weightStr), // e.g., "13.4 lbs"
                          ],
                        ),
                        const SizedBox(height: 8),
                        // Overload
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('Overloaded?', style: Theme.of(context).textTheme.bodyLarge),
                            Text(
                              overloaded ? 'YES (> ${threshold.toStringAsFixed(1)} lb)' : 'No',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: overloaded ? Colors.red : Colors.green,
                              ),
                            ),
                          ],
                        ),

                        const SizedBox(height: 24),
                        // Actions
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                          children: [



                            ElevatedButton.icon(
                              onPressed: conn == 'connected' ? null : () => ble.scanAndConnect(),
                              icon: const Icon(Icons.bluetooth_searching),
                              label: const Text('Scan & Connect'),
                            ),
                            ElevatedButton.icon(
                              onPressed: conn == 'connected' ? () => ble.disconnect() : null,
                              icon: const Icon(Icons.link_off),
                              label: const Text('Disconnect'),
                            ),



                          ],
                        ),
                      ],
                    ),
                  ),
                ),

                  // --- NEW: SELF TEST BUTTON ---
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0),
                    child: Align(
                      alignment: Alignment.centerRight,
                      child: ElevatedButton.icon(
                        icon: const Icon(Icons.play_circle_outline),
                        label: const Text('Run Rover Test'),
                        onPressed: () async {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Running Rover self-test...')),
                          );

                          //await diag.runBleSelfTest(ref);
                          await runBleSelfTest(ref);
                          


                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Self-test complete')),
                            );
                          }
                        },
                      ),
                    ),
                  ),

                  const SizedBox(height: 8),


                // --- NEW: TRIPS DISTANCE GRAPH CARD ---
                Consumer(
                  builder: (context, ref, _) {
                    final tripsAsync = ref.watch(tripsStreamProvider);
                    final totalKm = ref.watch(totalDistanceKmProvider);

                    return Card(
                      elevation: 2,
                      margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: tripsAsync.when(
                          loading: () => const SizedBox(
                            height: 160,
                            child: Center(child: CircularProgressIndicator()),
                          ),
                          error: (e, _) => SizedBox(
                            height: 160,
                            child: Center(child: Text('Error loading trips: $e')),
                          ),
                          data: (trips) {
                            if (trips.isEmpty) {
                              return const SizedBox(
                                height: 80,
                                child: Center(child: Text('No trips yet')),
                              );
                            }
                            return Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Distance per Trip (km)',
                                  style: Theme.of(context).textTheme.titleMedium,
                                ),
                                const SizedBox(height: 12),
                                SizedBox(
                                  height: 200,
                                  child: TripsDistanceChart(trips: trips),
                                ),
                                const SizedBox(height: 12),
                                Text(
                                  'Total distance (this user): ${totalKm.toStringAsFixed(2)} km',
                                  style: Theme.of(context).textTheme.bodyLarge,
                                ),
                              ],
                            );
                          },
                        ),
                      ),
                    );
                  },
                ),





// --- BIG PROFILE + TRIP LOGGER BUTTONS BELOW GRAPH ---
Padding(
  padding: const EdgeInsets.symmetric(horizontal: 16),
  child: Row(
    children: [
      Expanded(
        child: ElevatedButton(
          style: ElevatedButton.styleFrom(
            padding: const EdgeInsets.symmetric(vertical: 20),
            textStyle: const TextStyle(fontSize: 18),
          ),
          onPressed: () {
            Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const ProfilePage()),
            );
          },
          child: const Text("Profile"),
        ),
      ),
      const SizedBox(width: 16),
      Expanded(
        child: ElevatedButton(
          style: ElevatedButton.styleFrom(
            padding: const EdgeInsets.symmetric(vertical: 20),
            textStyle: const TextStyle(fontSize: 18),
          ),
          onPressed: () {
            Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const TripLoggerPage()),
            );
          },
          child: const Text("Trip Logger"),
        ),
      ),
    ],
  ),
),
const SizedBox(height: 16),




// --- NEW: D-PAD MANUAL CONTROL BUTTON ---
Padding(
  padding: const EdgeInsets.symmetric(horizontal: 16),
  child: SizedBox(
    width: double.infinity, // Makes the button span the whole width
    child: ElevatedButton.icon(
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 20),
        backgroundColor: Colors.blueGrey.shade800, // Gives it a nice tech look
        foregroundColor: Colors.white,
        textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
      ),
      onPressed: () {
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const DPadPage()),
        );
      },
      icon: const Icon(Icons.gamepad),
      label: const Text("Manual Rover Control"),
    ),
  ),
),
const SizedBox(height: 32),





              ],
            ),
          ),
        ),
      ),


    );


    
  }
}



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


