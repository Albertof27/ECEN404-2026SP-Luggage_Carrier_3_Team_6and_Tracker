package com.albertoflores.roverapp

// --- Imports ---
import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel




//were actually making the kotlin side that communicates with the dart here
class MainActivity : FlutterActivity() {
    //this line starts to scan and connect to the actual ble signal
    private val BLE_METHOD = "rover/ble"
    //this line actually pushes information and communicates data with the ble
    private val BLE_EVENTS = "rover/ble/events"
    //this is for the app notifications
    private val NOTIFY_METHOD = "rover/notify"
    //used when you create a notification channel
    private val NOTIFY_CH_ID = "rover_alerts"
    //this line holds a spot for the ble connection
    private var ble: RoverBle? = null
    //This line will send back events or info to the dart code 
    private var sink: EventChannel.EventSink? = null
    override fun configureFlutterEngine(engine: FlutterEngine) {
        //this will wire the controls to work with flutter
        super.configureFlutterEngine(engine)
        //now we create a eventchannel for continous ble scanning and notifications
        EventChannel(engine.dartExecutor.binaryMessenger, BLE_EVENTS).setStreamHandler(object: EventChannel.StreamHandler {
            //this starts listining to the scanning stream
            override fun onListen(args: Any?, s: EventChannel.EventSink?) { sink = s }
            //this stops listining which is important so that it prevents leaks
            override fun onCancel(args: Any?) { sink = null }
        })
        //this is what actually recieves the commands from dart in methodchannel and the result is how we respond
        MethodChannel(engine.dartExecutor.binaryMessenger, BLE_METHOD).setMethodCallHandler { call, result ->
            when (call.method) {
                "requestPermissions" -> {
                    //this is what happens when dart calls the request permissions functions
                    //this creates a list of perms that the app will need
                    val perms = mutableListOf<String>()
                    //for newer androids the app will reqyest newer perms that the older androids don't understand it put them in the list
                    if (Build.VERSION.SDK_INT >= 31)
                        perms += listOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
                    //asking for permissions for old androids and adding them to the list of perms
                    else
                        perms += Manifest.permission.ACCESS_FINE_LOCATION
                    if (Build.VERSION.SDK_INT >= 33)
                        ActivityCompat.requestPermissions(this, perms.toTypedArray(), 2000)
                     result.success(null)
                }


                //fakeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee


"startScan" -> {
    // Match Dart: BleBridge.startScan(serviceUuids: [...])
    val services = call.argument<List<String>>("serviceUuids") ?: emptyList()

    // Create RoverBle once, reuse afterwards
    ble = ble ?: RoverBle(this) { payload -> sink?.success(payload) }

    // Safe call here; ble is non-null at this point, but no need for !!
    ble?.startScan(services)

    result.success(null)
}


//fakeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee



/* 
                //the dart dunction start scan is called
                 "startScan" -> {
                    //gets all the UIDS to filter scan
                    val services = call.argument<List<String>>("services") ?: emptyList()
                    //val id = call.argument("id")!!
                    val id = call.argument<String>("id")!!
                    //this is creating a bluetooth varible if one does not already exsist and if it does it just uses the one already made  
                    //this line is whats actually getting the data from the esp32 which is the payload

                    ble = ble ?: RoverBle(this) { payload -> sink?.success(payload) }
                    //ble = ble ?: RoverBle(this) { payload: Map<String, Any?> ->
                       // sink?.success(payload)
                    //}
                    //starts scanning
                    ble!!.startScan(services)
                    //the payload is in dart now
                    result.success(null)
                 }

*/







                 //this stops scanning
                 "stopScan" -> { ble?.stopScan(); result.success(null) }
                 //connects to the device with the id
                 "connect" -> {
                    //the rover esp32 will emit the connection state using events
                    ble?.connect(call.argument<String>("id")!!)
                    result.success(null)
                 }
                 //disconnects any gatt conniction
                 "disconnect" -> { ble?.disconnect(); result.success(null) }
                 //this entire function below is asking for the secive updates (svc) and the characteristics(chr) so it can actually
                 //start recieving notifications from the esp32
                 "setNotify" -> {
                    ble?.setNotify(
                        call.argument("svc")!!,
                        call.argument("chr")!!,
                        call.argument<Boolean>("enable")!!
                    )
                    result.success(null)
                 }
                 //this parts just reads the notificcations that were aquired from the above function
                 //"read" -> ble?.read(call.argument("svc"),call.argument("chr"),result)
                 "read" -> ble?.read(
                    call.argument<String>("svc")!!, // Explicitly cast to String
                    call.argument<String>("chr")!!, //  Explicitly cast to String
                    result
                )
                 "write" -> ble?.write(
                    call.argument("svc"),
                    call.argument("chr"),
                    call.argument<List<Int>>("val")!!,
                    call.argument<Boolean>("withResp") ?: true,
                    result
                 )
                 //reads Rssi data
                 "readRssi" -> ble?.readRssi(result) ?: result.error("ble","not connected",null)
                 else -> result.notImplemented()
            }
        }
        //this is the method channel for the notifications of the app
        MethodChannel(engine.dartExecutor.binaryMessenger, NOTIFY_METHOD).setMethodCallHandler { call, result ->
            //this creates notifications channel which will be used
            when (call.method) {
                "requestPermission" -> {
                    ensureNotifyChannel()
                    result.success(null)
                }
                //this is the dart function that will be called for the notifications
                "showInstant" -> {
                    //this checks that the channel exsists before sending a notification
                    ensureNotifyChannel()
                    //these next two lines extract the proper information from the notification and classifies them
                    val title = call.argument<String>("title") ?: "Alert"
                    val body  = call.argument<String>("body")  ?: ""
                    //actually builds the notification
                    showNotification(title, body)
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
    }
    //this is the notification channel for newer androids 
    private fun ensureNotifyChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            //this will grab the system notification manager
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            //matches the notification ID and displays the user visable channel name
            val ch = NotificationChannel(NOTIFY_CH_ID, "Rover Alerts", NotificationManager.IMPORTANCE_HIGH)
            //this creates the notification
            nm.createNotificationChannel(ch)
        }
    }
    //this is the system that actually displays the notifications
    private fun showNotification(title: String, body: String) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        //this is the function that makes the notification
        val n = NotificationCompat.Builder(this, NOTIFY_CH_ID)
            //this is the small logo for the app
            .setSmallIcon(android.R.drawable.stat_sys_warning)
            //title and body from the dart code
            .setContentTitle(title)
            .setContentText(body)
            //this is the prioty level that should depend on the user settings
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            //the autocancel removes the notification when the user taps on it
            .setAutoCancel(true)
            .build()
        //the notification is postd with a unique id because diffrent ids avoid overriding old notifications
        nm.notify((System.currentTimeMillis() % 1_000_000).toInt(), n)
    }

}
