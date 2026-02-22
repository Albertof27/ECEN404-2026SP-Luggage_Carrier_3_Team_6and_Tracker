//imports values that can be called in the future like future and stream, where future is a single future value and stream
//is continious values in the future that will come
import 'dart:async';
//the next import gives you methodchannel and event channel which allows flutter to talk to native andrid language like kotlin
//and kotlin returns the values
import 'package:flutter/services.dart';
class BleBridge {
  //its static which means you can call it whenever and in kotlin you'll call this method in kotlin to scan for ble
  //its a very tiny varible name because it's supposed to be private
  static const _m = MethodChannel('rover/ble');
  //this is to allow the stream of notifications to work
  static const _events = EventChannel('rover/ble/events');
  // Notifications (Dart -> Android) — uses your Kotlin NOTIFY_METHOD = "rover/notify"
  static const MethodChannel _notify = MethodChannel('rover/notify');
  //the line below actually subscribes to the stram of notification and will return the stream of info
  static Stream<dynamic> events() => _events.receiveBroadcastStream();
  //this is the part where the fluuter will actually ask for permissions from the app(native android)
  static Future<void> requestPermissions() =>
    _m.invokeMethod('requestPermissions');
  //This is when the app starts scanning for the BLE signal


  static Future<void> startScan({List<String> serviceUuids = const []}) =>
  _m.invokeMethod('startScan', {
    'serviceUuids': serviceUuids, //  match Kotlin side
  });


  //static Future<void> startScan({List<String> serviceUuids = const []}) =>
    //_m.invokeMethod('startScan', {'services': serviceUuids});





  //this will tell the app to stop scanning and also invoke method is just the function that allows dart to talk to android
  static Future<void> stopScan() => _m.invokeMethod('stopScan');
  //this part asks the android to connect a device(the esp32) 
  static Future<void> connect(String id) =>
    _m.invokeMethod('connect', {'id': id});
  //this part twlls the android to disconnect
   static Future<void> disconnect() => _m.invokeMethod('disconnect');
   //enables and disables notifications in the ble sense so this is just when data is transferred from the esp 32 to app
   static Future<void> setNotify(String svc, String chr, bool enable) =>
    _m.invokeMethod('setNotify', {'svc': svc, 'chr': chr, 'enable': enable});
  //this allows the phone to actually read data from the esp32
  static Future<List<int>> read(String svc, String chr) async =>
    List<int>.from(await _m.invokeMethod('read', {'svc': svc, 'chr': chr}));
  //the app writes down the info for the specific characteristics of the esp32
  static Future<void> write(String svc, String chr, List<int> val, {bool withResponse=true}) =>
    _m.invokeMethod('write', {'svc': svc, 'chr': chr, 'val': val, 'withResp': withResponse});
  //this function reads the rssi value which is responsible for tracking location and its a function because dart expects
  // an int so you need to specificly state that
  static Future<int> readRssi() async {
    final result = await _m.invokeMethod('readRssi');
    return result as int;
  }

  
  // ===== Notifications API (matches your Kotlin MainActivity) =====
  /// Ensure notification channel/permission exists (Android 13+).
  static Future<void> notifyRequestPermission() =>
      _notify.invokeMethod('requestPermission');

  /// Show a one-shot high-importance notification.
  static Future<void> showInstant(String title, String body) =>
      _notify.invokeMethod('showInstant', {'title': title, 'body': body});


}

