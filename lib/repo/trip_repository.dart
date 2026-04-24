import 'dart:async';
import 'package:hive/hive.dart';
import 'package:uuid/uuid.dart';
import 'package:rover_app/models/trip.dart';
import 'package:rover_app/models/track_point.dart';
import 'package:rover_app/utils/geo.dart';

class TripRepository {
  
  late final String _tripsBoxName;
  late final String _pointsBoxName;

  late final Box<Trip> _trips;
  late final Box<TrackPoint> _points;

  TripRepository._(this._trips, this._points, this._tripsBoxName, this._pointsBoxName);

  static Future<TripRepository> initForUser(String uid) async {
    final tripsBox = 'trips_$uid';
    final pointsBox = 'points_$uid';

    final trips = await Hive.openBox<Trip>(tripsBox);
    final points = await Hive.openBox<TrackPoint>(pointsBox);

    return TripRepository._(trips, points, tripsBox, pointsBox);
  }

  Future<void> close() async {
    if (_trips.isOpen) await _trips.close();
    if (_points.isOpen) await _points.close();
  }

  Stream<List<Trip>> getTripsStream() async* {
    yield getAllTrips();
    await for (final _ in _trips.watch()) {
      yield getAllTrips();
    }
  }

  Future<Trip> createTrip(String name) async {
    final t = Trip(
      id: const Uuid().v4(),
      name: name,
      startedAt: DateTime.now().toUtc(),
    );
    await _trips.put(t.id, t);
    return t;
  }

  Future<void> insertPoint(TrackPoint p) async {
    await _points.add(p);

    final trip = _trips.get(p.tripId);
    if (trip == null) return;

    final pts = await getPointsForTrip(p.tripId, limitLastN: 2);
    if (pts.length == 2) {
      final d = haversine(pts[0].lat, pts[0].lon, pts[1].lat, pts[1].lon);
      trip.distanceMeters += d;
    }
    trip.pointCount += 1;
    await trip.save();
  }

  Future<List<TrackPoint>> getPointsForTrip(String tripId, {int? limitLastN}) async {
    final pts = _points.values.where((e) => e.tripId == tripId).toList()
      ..sort((a, b) => a.tsUtc.compareTo(b.tsUtc));
    if (limitLastN != null && pts.length > limitLastN) {
      return pts.sublist(pts.length - limitLastN);
    }
    return pts;
  }

  Future<void> finalizeTrip(String tripId, {double simplifyToleranceM = 5}) async {
    final trip = _trips.get(tripId);
    if (trip == null) return;

    final pts = await getPointsForTrip(tripId);
    final simplified = simplifyDouglasPeucker(pts, simplifyToleranceM);

    if (simplified.length != pts.length) {
      final toDelete = _points.keys
          .where((k) => (_points.get(k) as TrackPoint).tripId == tripId)
          .toList();
      await _points.deleteAll(toDelete);
      for (final p in simplified) {
        await _points.add(p);
      }
      trip.pointCount = simplified.length;

      double dist = 0;
      for (int i = 1; i < simplified.length; i++) {
        dist += haversine(
          simplified[i - 1].lat, simplified[i - 1].lon,
          simplified[i].lat, simplified[i].lon,
        );
      }
      trip.distanceMeters = dist;
    }

    trip.endedAt = DateTime.now().toUtc();
    await trip.save();
  }

  List<Trip> getAllTrips() {
    final list = _trips.values.toList()
      ..sort((a, b) => b.startedAt.compareTo(a.startedAt));
    return list;
  }

  Future<void> deleteTrip(String tripId) async {
    final toDelete = _points.keys
        .where((k) => (_points.get(k) as TrackPoint).tripId == tripId)
        .toList();
    await _points.deleteAll(toDelete);
    await _trips.delete(tripId);
  }
}

