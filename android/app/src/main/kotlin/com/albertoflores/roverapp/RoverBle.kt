package com.albertoflores.roverapp
//the package is how andoid shorts the data so make sure it matches
//all these imports and native BLE APIs that you can call and that you will need to make
import android.bluetooth.*
import android.bluetooth.le.*
import android.content.Context
import android.os.ParcelUuid
import android.os.Handler
import android.os.Looper
import io.flutter.plugin.common.MethodChannel
//so you can go through UUID's
import java.util.UUID
//function that manages the activity which provides important context like if it has the proper permissions and it has thr right imports
//emit is awhat sends structered data back to the dart side of things
class RoverBle(
    //private val activity: MainActivity,
    private val context: Context,
    private val emit: (Map<String, Any?>) -> Unit
) {
    //these values give you access to the scanner which you need to find the signal 
    private val manager = context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
    //private val manager = activity.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
    private val adapter = manager.adapter
    private var scanner: BluetoothLeScanner? = null
    private var gatt: BluetoothGatt? = null

    // Pending async completions for Dart MethodChannel calls
    //these are the other side to all the future vaaribles we have in dart, they will be filled by these varibles.
    private var pendingRead: MethodChannel.Result? = null
    private var pendingWrite: MethodChannel.Result? = null
    private var pendingRssi: MethodChannel.Result? = null




    private fun safeEmit(data: Map<String, Any?>) {
    Handler(Looper.getMainLooper()).post {
        emit(data)
    }
}

    // -------- Scanning --------
    //this starts scanning and it's looking for uuids
    fun startScan(uuids: List<String>) {
        //this function Tries to get the system’s BLE scanner from the Bluetooth adapter 
        val le = adapter.bluetoothLeScanner ?: run {
            emit(mapOf("type" to "scanError", "code" to -1, "msg" to "No scanner"))
            return
        }
        //store it in a local varible named le and also in scanner so you can reuse the varible even if the scan is over
        scanner = le
        //these filters look for what theyre scanning
        val filters =
            //if the uuid is empty it just scans for everything
            if (uuids.isEmpty()) emptyList()
            //if the thing being scanned has a uuid the scanner will take in translate it into a android varible and the filtering saves power and is fast
            else uuids.map {
                ScanFilter.Builder()
                    .setServiceUuid(ParcelUuid(UUID.fromString(it)))
                    .build()
            }
        //this entire function is the scan settings for how aggressive the scanner should scan(scan_mode_low_latency is the fastest one and takes up power)
        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()
        //this is what actually starts scanning
        le.startScan(filters, settings, scanCb)
        //this is what's sent back to the flutter side for the user
        emit(mapOf("type" to "scanStarted"))
    }
    //stops scanning to save battery
    fun stopScan() {
        scanner?.stopScan(scanCb)
        emit(mapOf("type" to "scanStopped"))
    }
    //this will list out the scanned rover details to the user
    private val scanCb = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, res: ScanResult) {
            safeEmit(
                mapOf(
                    "type" to "scanResult",
                    "id" to res.device.address,
                    "name" to (res.device.name ?: "")
                )
            )
        }
        //!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        override fun onScanFailed(errorCode: Int) {
            safeEmit(mapOf("type" to "scanError", "code" to errorCode))
        }
    }

    // -------- Connection --------
    //this establishes the GAAT sesh to read/write/notify
    fun connect(id: String) {
        stopScan()
        //gatt = adapter.getRemoteDevice(id).connectGatt(activity, false, gattCb)
        gatt = adapter.getRemoteDevice(id).connectGatt(context, false, gattCb, BluetoothDevice.TRANSPORT_LE)
        emit(mapOf("type" to "connState", "state" to "connecting"))
    }
    //this disconnects the sesh to avoid leaks and so it can reconnect to something else
    fun disconnect() {
        gatt?.disconnect()
        gatt?.close()
        gatt = null
        emit(mapOf("type" to "connState", "state" to "disconnected"))
    }
    
    private val gattCb = object : BluetoothGattCallback() {
        //the function checks to see if anything is connected and if it is then it displays services and characterstics by emitting a "map" back to the dart side
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                g.close() 
                if (gatt == g) gatt = null
                safeEmit(mapOf("type" to "connError", "status" to status))
                safeEmit(mapOf("type" to "connState", "state" to "disconnected"))
                return
            }
            //handles when it goes from connected to disconnected or a new state and sends info to the app
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                safeEmit(mapOf("type" to "connState", "state" to "connected"))
                g.discoverServices()
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                g.close()
                if (gatt == g) gatt = null
                safeEmit(mapOf("type" to "connState", "state" to "disconnected"))
            }
        }
        //this function is good for troubleshooting because it says if the discovery is done  
        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                safeEmit(mapOf("type" to "services", "count" to g.services.size))
            } else {
                safeEmit(mapOf("type" to "servicesError", "status" to status))
            }
        }
        //this is the function that would actually send the rover data to the user app
        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic) {
            safeEmit(
                mapOf(
                    "type" to "notify",
                    "svc" to c.service.uuid.toString(),
                    "chr" to c.uuid.toString(),
                    "val" to (c.value?.toList() ?: emptyList<Int>())
                )
            )
        }
        //the read write and rssi functions complete all the pending futures in methodchannel
        override fun onCharacteristicRead(
            //g and c are just the symbols 
            g: BluetoothGatt,
            c: BluetoothGattCharacteristic,
            status: Int
        ) {

            val result = pendingRead
            pendingRead = null
            val bytes = c.value?.toList() ?: emptyList<Int>()


            Handler(Looper.getMainLooper()).post {
                    if (status == BluetoothGatt.GATT_SUCCESS) {
                        result?.success(bytes)
                        emit(mapOf("type" to "read", "svc" to c.service.uuid.toString(), "chr" to c.uuid.toString(), "val" to bytes))
                    } else {
                        result?.error("ble", "read status $status", null)
                    }
                }
            }

/* 
            if (status == BluetoothGatt.GATT_SUCCESS) {
                val bytes = c.value?.toList() ?: emptyList<Int>()
                pendingRead?.success(bytes)
                safeEmit(
                    mapOf(
                        "type" to "read",
                        "svc" to c.service.uuid.toString(),
                        "chr" to c.uuid.toString(),
                        "val" to bytes
                    )
                )
            } else {
                pendingRead?.error("ble", "read status $status", null)
            }
            //always clear out the varible so it doesnt break later
            pendingRead = null
        }
        */

        override fun onCharacteristicWrite(
            g: BluetoothGatt,
            c: BluetoothGattCharacteristic,
            status: Int
        ) {

            val result = pendingWrite
            pendingWrite = null

            Handler(Looper.getMainLooper()).post {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                result?.success(null)
            } else {
                result?.error("ble", "write status $status", null)
            }
        }
    }
    /* 
            if (status == BluetoothGatt.GATT_SUCCESS) {
                pendingWrite?.success(null)
            } else {
                pendingWrite?.error("ble", "write status $status", null)
            }
            pendingWrite = null
        }
         */

        override fun onReadRemoteRssi(g: BluetoothGatt, rssi: Int, status: Int) {
            val result = pendingRssi
            pendingRssi = null

            Handler(Looper.getMainLooper()).post {
                if (status == BluetoothGatt.GATT_SUCCESS) {
                    result?.success(rssi)
                    emit(mapOf("type" to "rssi", "value" to rssi))
                } else {
                    result?.error("ble", "rssi status $status", null)
                }
            }
            


            pendingRssi = null
        }
    }

    // -------- GATT Operations --------
    //this function is whats responsible for enabling and disabling the notifications
    fun setNotify(svc: String, chr: String, enable: Boolean) {
        // this is getting the respective info from the rover
        val s = gatt?.getService(UUID.fromString(svc)) ?: return
        val c = s.getCharacteristic(UUID.fromString(chr)) ?: return

        // Enable/disable local notification listener
        gatt?.setCharacteristicNotification(c, enable)

        // Write CCCD descriptor to tell the peripheral to start/stop notifications
        val ccc = c.getDescriptor(UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"))
        if (ccc != null) {
            ccc.value = if (enable)
                BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            else
                BluetoothGattDescriptor.DISABLE_NOTIFICATION_VALUE
            gatt?.writeDescriptor(ccc)
        }
    }
    //these next functions focus on forfilling the future values that dart has and then it zeros them out so these fire after the bluetooth connection
    //is done and it satisfies the future streams that rquire ct data

    fun read(svc: String?, chr: String?, result: MethodChannel.Result) {
        val s = gatt?.getService(UUID.fromString(svc)) ?: run {
            result.error("ble", "no svc", null); return
        }
        val c = s.getCharacteristic(UUID.fromString(chr)) ?: run {
            result.error("ble", "no chr", null); return
        }

        pendingRead = result
        if (gatt?.readCharacteristic(c) != true) {
            pendingRead = null
            result.error("ble", "read failed", null)
        }
    }

    fun write(
        svc: String?,
        chr: String?,
        valBytes: List<Int>,
        withResp: Boolean,
        result: MethodChannel.Result
    ) {
        val s = gatt?.getService(UUID.fromString(svc)) ?: run {
            result.error("ble", "no svc", null); return
        }
        val c = s.getCharacteristic(UUID.fromString(chr)) ?: run {
            result.error("ble", "no chr", null); return
        }

        c.value = valBytes.map { it.toByte() }.toByteArray()
        c.writeType = if (withResp)
            BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
        else
            BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE

        pendingWrite = result
        if (gatt?.writeCharacteristic(c) != true) {
            pendingWrite = null
            result.error("ble", "write failed", null)
        }
    }

    fun readRssi(result: MethodChannel.Result) {
        pendingRssi = result
        val ok = gatt?.readRemoteRssi() ?: false
        if (!ok) {
            pendingRssi = null
            result.error("ble", "rssi failed", null)
        }
    }
}

