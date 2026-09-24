// EarbudButtons: background app that owns the Bluetooth headset buttons by registering as the
// macOS "Now Playing" app, and maps them to voice2clipboard gestures.
//   single press  -> "pause"         -> on_gesture.sh single
//   double press  -> "nextTrack"     -> on_gesture.sh double
//   triple press  -> "previousTrack" -> on_gesture.sh triple
// Long presses change volume on the headset itself and never reach the Mac as commands.
// Whichever app last STARTED playing owns the buttons, and keeps them while paused. Verified on
// 2026-09-20 with two silent test clients: setting the Now Playing info again, or setting
// playbackState = .playing when it already is, takes nothing back; only a paused -> playing
// transition does (claimNowPlaying). The app claims at start, on headset connect and on SIGUSR1.
// Watchdog: mediaremoted logs every change of owner ("ActiveNowPlayingClient changed from X to
// Y"), and that log is the only way to know, since the private MediaRemote queries answer
// nothing to unentitled apps (macOS 15.4+). The app follows that line.
// Policy (Remi, 2026-09-20 evening): while the headset is connected the buttons are ALWAYS ours.
// He never uses them for media, so the earlier rule "during a video a press pauses the video" is
// withdrawn. When another app takes the buttons they are taken back half a second later (with a
// back-off if an app insists), and as a safety net the claim is repeated every minute even when
// all looks well, in case a log line was missed. A claim sends nothing to the other app: its
// video keeps playing. The earlier design waited for 30 s of silent output first, and on
// 2026-09-20 20:00 that never came: a browser tab held an output stream open, so the buttons
// stayed with a paused QuickTime for 3.5 minutes. The health flag "nowplaying" is raised only
// when taking back has not worked for 15 s. Without the headset nothing is taken back: the
// keyboard's play key is then the only "button" and should keep resuming his video.
// It also watches Bluetooth connections: every connect and disconnect is handed to
// on_headset.sh, which stops a dictation when the headset drops and runs a self-check with a
// ready / not ready cue when it comes back.
// Last, it watches the headset's microphone: whenever a process opens or closes it, the state is
// written to runtime/secretary/headset_mic and on_headset.sh is told (mic-open / mic-closed). An
// open headset microphone means call mode, where the buttons no longer reach the Mac; whether
// that is a dictation or a stray program is for the scripts to decide.
import AppKit
import CoreAudio
import IOBluetooth
import MediaPlayer

let gestureScript = CommandLine.arguments.count > 1
    ? CommandLine.arguments[1]
    : "/Users/remi/voice2clipboard/scripts/mac/secretary/on_gesture.sh"
let env = ProcessInfo.processInfo.environment
let headsetScript = "/Users/remi/voice2clipboard/scripts/mac/secretary/on_headset.sh"
// Test instances (local_tests/test_nowplaying_watchdog.sh) log elsewhere and ignore Bluetooth.
let testMode = env["EARBUDS_TEST"] == "1"
let logPath = env["EARBUDS_LOG"] ?? "/Users/remi/voice2clipboard/runtime/secretary/earbuds.log"
let healthDir = env["EARBUDS_HEALTH_DIR"] ?? "/Users/remi/voice2clipboard/runtime/secretary/health"
let reclaimDelayS = Double(env["EARBUDS_RECLAIM_DELAY_S"] ?? "") ?? 0.5   // theft -> take-back
let assertEveryS = Double(env["EARBUDS_ASSERT_EVERY_S"] ?? "") ?? 60        // safety-net claim
let stuckAfterS = Double(env["EARBUDS_STUCK_AFTER_S"] ?? "") ?? 15          // then the health flag
// Resting in "paused" (2026-09-21, two tests with Remi): the headset keeps its own idea of whether
// music plays. Told "playing" all day, it sends Pause when an earbud goes into the charger, which
// is what a single press sends too, so a dictation started by itself. Told "paused", docking
// sends nothing and a press arrives as Play. So "playing" is only said for the instant needed to
// take the buttons; then the app rests in "paused" and says so again after every command.
// Play is a real press; Pause is handed to on_gesture.sh as "pause", which decides (a message
// playing: pause it; nothing playing: the headset was put away, no dictation).
// If resting loses the buttons to an app that is really playing, "playing" is held for a while
// instead (the behaviour before this change), so this can never be worse than it was.
let restPaused = env["EARBUDS_REST_PAUSED"] != "0"
let settleAfterS = Double(env["EARBUDS_SETTLE_AFTER_S"] ?? "") ?? 0.4
let holdPlayingS = Double(env["EARBUDS_HOLD_PLAYING_S"] ?? "") ?? 120
let micStatePath = env["EARBUDS_MIC_STATE"] ?? "/Users/remi/voice2clipboard/runtime/secretary/headset_mic"

func stamp() -> String {
    let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd HH:mm:ss.SSS"; return f.string(from: Date())
}
func log(_ s: String) {
    let line = "\(stamp()) \(s)\n"
    print(line, terminator: ""); fflush(stdout)
    if let h = FileHandle(forWritingAtPath: logPath) {
        h.seekToEndOfFile(); h.write(line.data(using: .utf8)!); h.closeFile()
    } else {
        FileManager.default.createFile(atPath: logPath, contents: line.data(using: .utf8))
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let info = MPNowPlayingInfoCenter.default()

func assertNowPlaying() {
    info.nowPlayingInfo = [
        MPMediaItemPropertyTitle: "voice2clipboard",
        MPMediaItemPropertyArtist: "earbud buttons: 1 = speech, 2 = dictate, 3 = repeat",
        MPMediaItemPropertyPlaybackDuration: 36000.0,
        MPNowPlayingInfoPropertyElapsedPlaybackTime: 0.0,
        MPNowPlayingInfoPropertyPlaybackRate: 1.0,
    ]
    info.playbackState = .playing
}
// Takes the buttons back from another app: only a paused -> playing transition does that.
var lastClaimAt = Date.distantPast
var lastSettleAt = Date.distantPast      // when we last went to rest in "paused"
var holdPlayingUntil = Date.distantPast  // resting lost the buttons to a playing app: stay "playing"
var lostWhileResting = 0
func settle() {
    guard restPaused, Date() >= holdPlayingUntil else { return }
    info.playbackState = .paused
    lastSettleAt = Date()
}
func settleSoon() { DispatchQueue.main.asyncAfter(deadline: .now() + settleAfterS) { settle() } }
func claimNowPlaying() {
    lastClaimAt = Date()
    info.playbackState = .paused
    assertNowPlaying()
    settleSoon()
}

var lastGestureAt = Date.distantPast
func fire(_ gesture: String) {
    let now = Date()
    if now.timeIntervalSince(lastGestureAt) < 0.25 { log("ignored duplicate \(gesture)"); return }
    lastGestureAt = now
    log("gesture \(gesture)")
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/bin/bash")
    p.arguments = [gestureScript, gesture]
    p.standardOutput = FileHandle.nullDevice; p.standardError = FileHandle.nullDevice
    do { try p.run() } catch { log("failed to run \(gestureScript): \(error)") }
    // playing, then paused again a moment later: the change is what tells the headset "paused"
    assertNowPlaying()
    settleSoon()
}

let center = MPRemoteCommandCenter.shared()
let mapping: [(MPRemoteCommand, String, String)] = [
    (center.pauseCommand, "pause", restPaused ? "pause" : "single"),
    (center.playCommand, "play", "single"),
    (center.togglePlayPauseCommand, "togglePlayPause", "single"),
    (center.nextTrackCommand, "nextTrack", "double"),
    (center.previousTrackCommand, "previousTrack", "triple"),
]
for (cmd, name, gesture) in mapping {
    cmd.isEnabled = true
    cmd.addTarget { _ in
        log("command \(name)")
        fire(gesture)
        return .success
    }
}
for cmd in [center.stopCommand, center.seekForwardCommand, center.seekBackwardCommand,
            center.skipForwardCommand, center.skipBackwardCommand, center.changePlaybackPositionCommand] {
    cmd.isEnabled = true
    cmd.addTarget { _ in log("command (unmapped) \(cmd)"); return .success }
}

func runScript(_ script: String, _ args: [String]) {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/bin/bash")
    p.arguments = [script] + args
    p.standardOutput = FileHandle.nullDevice; p.standardError = FileHandle.nullDevice
    do { try p.run() } catch { log("failed to run \(script): \(error)") }
}

// Bluetooth connect / disconnect. The connect notification also fires once at start for devices
// that are already connected, which registers their disconnect notification.
// Buttons are only taken back from another app while the earbuds are connected: without them
// the keyboard's play key is the only "button", and it should keep resuming his paused video.
let headsetPattern = env["VOICE2CLIPBOARD_HEADSET_PATTERN"] ?? "Shokz|OpenFit"
func isHeadset(_ name: String) -> Bool { name.range(of: headsetPattern, options: [.regularExpression, .caseInsensitive]) != nil }
var headsetConnected = testMode
var registeredAt: Date? = nil   // when the connect-notification registration returned

final class BluetoothWatcher: NSObject {
    @objc func connected(_ note: IOBluetoothUserNotification, device: IOBluetoothDevice) {
        let name = device.name ?? "unknown"
        log("bluetooth connected: \(name)")
        if isHeadset(name) { headsetConnected = true }
        device.register(forDisconnectNotification: self, selector: #selector(disconnected(_:device:)))
        // Devices already connected when this app starts are reported during the registration
        // call: that is a restart of the app, not Remi putting the headset on, and must not sound
        // like an event. (The call itself can take 10 s on the first launch of a new build, so
        // "time since the process started" says nothing.)
        let atStart = registeredAt == nil || Date().timeIntervalSince(registeredAt!) < 2
        runScript(headsetScript, [atStart ? "present" : "connected", name])
        claimNowPlaying()
    }
    @objc func disconnected(_ note: IOBluetoothUserNotification, device: IOBluetoothDevice) {
        let name = device.name ?? "unknown"
        log("bluetooth disconnected: \(name)")
        if isHeadset(name) { headsetConnected = false }
        note.unregister()
        runScript(headsetScript, ["disconnected", name])
    }
}
let bluetoothWatcher = BluetoothWatcher()
if testMode {
    log("test mode: Bluetooth events ignored")
} else if IOBluetoothDevice.register(forConnectNotifications: bluetoothWatcher,
                              selector: #selector(BluetoothWatcher.connected(_:device:))) == nil {
    log("bluetooth notifications unavailable (permission missing?); buttons still work")
}
registeredAt = Date()

var signalSources: [DispatchSourceSignal] = []
signal(SIGUSR1, SIG_IGN)
let usr1 = DispatchSource.makeSignalSource(signal: SIGUSR1, queue: .main)
usr1.setEventHandler { log("SIGUSR1: claiming Now Playing"); claimNowPlaying() }
usr1.resume()
// SIGUSR2 (ctl.sh settle, sent by say_now.sh when a message ends): audio makes the headset believe
// "playing" again for a few seconds; saying playing-then-paused tells it otherwise at once.
signal(SIGUSR2, SIG_IGN)
let usr2 = DispatchSource.makeSignalSource(signal: SIGUSR2, queue: .main)
usr2.setEventHandler { guard otherOwner == nil else { return }; assertNowPlaying(); settleSoon() }
usr2.resume()

// ---- Headset microphone watch ----
// CoreAudio answers these without any permission: which devices exist, whether one is running,
// and which processes run input on it (macOS 14.2+).
func audioProperty<T>(_ object: AudioObjectID, _ selector: AudioObjectPropertySelector, _ scope: AudioObjectPropertyScope, into value: inout T) -> Bool {
    var address = AudioObjectPropertyAddress(mSelector: selector, mScope: scope, mElement: kAudioObjectPropertyElementMain)
    var size = UInt32(MemoryLayout<T>.size)
    return withUnsafeMutablePointer(to: &value) { AudioObjectGetPropertyData(object, &address, 0, nil, &size, $0) } == noErr
}
func audioObjectList(_ object: AudioObjectID, _ selector: AudioObjectPropertySelector, _ scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal) -> [AudioObjectID] {
    var address = AudioObjectPropertyAddress(mSelector: selector, mScope: scope, mElement: kAudioObjectPropertyElementMain)
    var size = UInt32(0)
    guard AudioObjectGetPropertyDataSize(object, &address, 0, nil, &size) == noErr, size > 0 else { return [] }
    var list = [AudioObjectID](repeating: 0, count: Int(size) / MemoryLayout<AudioObjectID>.size)
    guard AudioObjectGetPropertyData(object, &address, 0, nil, &size, &list) == noErr else { return [] }
    return Array(list.prefix(Int(size) / MemoryLayout<AudioObjectID>.size))
}
func audioDeviceName(_ device: AudioObjectID) -> String {
    var name: Unmanaged<CFString>? = nil
    guard audioProperty(device, kAudioObjectPropertyName, kAudioObjectPropertyScopeGlobal, into: &name), let n = name else { return "" }
    return n.takeRetainedValue() as String
}
let systemAudio = AudioObjectID(kAudioObjectSystemObject)
func headsetInputDevice() -> AudioObjectID? {
    audioObjectList(systemAudio, kAudioHardwarePropertyDevices).first {
        isHeadset(audioDeviceName($0)) && !audioObjectList($0, kAudioDevicePropertyStreams, kAudioObjectPropertyScopeInput).isEmpty
    }
}
// pids of the processes running input on that device ("pid:executable" each)
func micHolders(_ device: AudioObjectID) -> [String] {
    var holders: [String] = []
    for process in audioObjectList(systemAudio, kAudioHardwarePropertyProcessObjectList) {
        var running = UInt32(0), pid = pid_t(0)
        guard audioProperty(process, kAudioProcessPropertyIsRunningInput, kAudioObjectPropertyScopeGlobal, into: &running), running != 0,
              audioProperty(process, kAudioProcessPropertyPID, kAudioObjectPropertyScopeGlobal, into: &pid) else { continue }
        let devices = audioObjectList(process, kAudioProcessPropertyDevices, kAudioObjectPropertyScopeInput)
        if !devices.isEmpty && !devices.contains(device) { continue }
        var path = [CChar](repeating: 0, count: 4096)
        let exe = proc_pidpath(pid, &path, UInt32(path.count)) > 0 ? URL(fileURLWithPath: String(cString: path)).lastPathComponent : "unknown"
        holders.append("\(pid):\(exe.replacingOccurrences(of: " ", with: "_"))")
    }
    return holders.sorted()
}
var micState = ""
func pollHeadsetMic() {
    var state = "absent"
    var deviceName = ""
    if let device = headsetInputDevice() {
        deviceName = audioDeviceName(device)
        var running = UInt32(0)
        _ = audioProperty(device, kAudioDevicePropertyDeviceIsRunningSomewhere, kAudioObjectPropertyScopeGlobal, into: &running)
        state = running != 0 ? "open\t" + micHolders(device).joined(separator: ",") : "closed"
    }
    guard state != micState else { return }
    let was = micState; micState = state
    try? "\(stamp().prefix(19))\t\(state)\n".write(toFile: micStatePath, atomically: true, encoding: .utf8)
    if state.hasPrefix("open") {
        log("headset microphone open: \(state.dropFirst(5))")
        if !testMode { runScript(headsetScript, ["mic-open", deviceName, String(state.dropFirst(5))]) }
    } else if was.hasPrefix("open") {
        log("headset microphone closed")
        if !testMode { runScript(headsetScript, ["mic-closed", deviceName.isEmpty ? "OpenFit (gone)" : deviceName]) }
    }
}

// ---- Now Playing watchdog ----
var healthText = ""
func setHealth(_ text: String) {
    guard text != healthText else { return }   // written on change only: owners can flap
    healthText = text
    try? FileManager.default.createDirectory(atPath: healthDir, withIntermediateDirectories: true)
    try? "\(stamp().prefix(19))\t\(text)\n".write(toFile: healthDir + "/nowplaying", atomically: true, encoding: .utf8)
}
// "... ActiveNowPlayingClient changed from origin-Mac-1/client-a-1/player-P to
//  origin-Mac-1/client-com.x.y-5384 (Name)/player-P"  ->  ("com.x.y", 5384); ("nobody", 0) for (null)
func parseOwner(_ line: String) -> (name: String, pid: Int32)? {
    guard let r = line.range(of: "ActiveNowPlayingClient changed from "),
          let to = line.range(of: " to ", range: r.upperBound..<line.endIndex) else { return nil }
    let rest = line[to.upperBound...]
    guard let c = rest.range(of: "client-") else { return ("nobody", 0) }
    let token = rest[c.upperBound...].prefix { $0 != "/" && $0 != " " }
    guard let dash = token.lastIndex(of: "-"), let pid = Int32(token[token.index(after: dash)...]) else { return ("nobody", 0) }
    return (String(token[..<dash]), pid)
}

var ownerSeen = false           // the log stream has told us who owns the buttons at least once
var otherOwner: String? = nil   // nil while the buttons are ours
var otherSince: Date? = nil     // since when they have not been ours
var reclaimDueAt: Date? = nil
var recentThefts: [Date] = []   // last minute, for the back-off and to keep the log short
var unloggedThefts = 0
var lastTheftSummaryAt = Date()
func reclaimIfDue() {
    guard otherOwner != nil, headsetConnected, let due = reclaimDueAt, Date() >= due else { return }
    reclaimDueAt = Date().addingTimeInterval(5)   // try again in 5 s if this claim does not take
    claimNowPlaying()
}
func ownerChanged(_ name: String, _ pid: Int32) {
    ownerSeen = true
    let now = Date()
    if pid == getpid() {
        if let other = otherOwner, recentThefts.count <= 5 { log("Now Playing is ours again (was \(other))") }
        otherOwner = nil; otherSince = nil; reclaimDueAt = nil; setHealth("ok")
        return
    }
    if otherOwner == nil { otherSince = now }
    otherOwner = name
    // taken right after we went to rest: that app is really playing, and mediaremoted prefers it
    if restPaused && now >= holdPlayingUntil && now.timeIntervalSince(lastSettleAt) < 3 {
        lostWhileResting += 1
        if lostWhileResting >= 2 {
            holdPlayingUntil = now.addingTimeInterval(holdPlayingS); lostWhileResting = 0
            log("resting in paused loses the buttons to \(name): holding playing for \(Int(holdPlayingS)) s (putting the headset away may start a dictation meanwhile)")
        }
    }
    guard headsetConnected else {
        log("Now Playing taken by \(name) (pid \(pid)): left alone, the headset is not connected")
        return
    }
    recentThefts = recentThefts.filter { now.timeIntervalSince($0) < 60 } + [now]
    let n = recentThefts.count
    let delay = n <= 3 ? reclaimDelayS : min(10, reclaimDelayS * pow(2, Double(n - 3)))
    // an app that insists (scrubbing a video) must not fill the log: five lines a minute, then a count
    if n <= 5 { log("Now Playing taken by \(name) (pid \(pid)): taking it back in \(delay) s") }
    else { unloggedThefts += 1 }
    reclaimDueAt = now.addingTimeInterval(delay)
    DispatchQueue.main.asyncAfter(deadline: .now() + delay + 0.01) { reclaimIfDue() }
}
let reclaimTimer = DispatchSource.makeTimerSource(queue: .main)
reclaimTimer.schedule(deadline: .now() + 2, repeating: 5.0, leeway: .seconds(1))
reclaimTimer.setEventHandler {
    let now = Date()
    pollHeadsetMic()
    if unloggedThefts > 0 && now.timeIntervalSince(lastTheftSummaryAt) >= 600 {
        log("Now Playing: \(unloggedThefts) more changes of owner taken back without a line each (last other owner: \(otherOwner ?? "none now"))")
        unloggedThefts = 0; lastTheftSummaryAt = now
    }
    guard headsetConnected else { return }
    if let other = otherOwner {
        if reclaimDueAt == nil { reclaimDueAt = now }   // e.g. taken while the headset was away
        reclaimIfDue()
        if let since = otherSince, now.timeIntervalSince(since) >= stuckAfterS {
            if healthText == "ok" || healthText.isEmpty { log("Now Playing: \(other) still holds the buttons after \(Int(stuckAfterS)) s of taking back") }
            setHealth("the earbud buttons currently control \(other), not the secretary, and taking them back is not working")
        }
    } else if now.timeIntervalSince(lastClaimAt) >= assertEveryS {
        if now.timeIntervalSince(lastSettleAt) > 30 { lostWhileResting = 0 }
        claimNowPlaying()   // safety net, silent: covers a change of owner the log stream missed
    }
}
reclaimTimer.resume()

let ownerPredicate = "process == \"mediaremoted\" AND eventMessage CONTAINS \"ActiveNowPlayingClient changed\""
var ownerStream: Process? = nil
func startOwnerStream() {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/log")
    p.arguments = ["stream", "--style", "compact", "--predicate", ownerPredicate]
    let pipe = Pipe()
    p.standardOutput = pipe; p.standardError = FileHandle.nullDevice
    var pending = ""
    pipe.fileHandleForReading.readabilityHandler = { h in
        let data = h.availableData
        guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
        DispatchQueue.main.async {
            pending += text
            while let nl = pending.firstIndex(of: "\n") {
                let line = String(pending[..<nl]); pending.removeSubrange(...nl)
                if let o = parseOwner(line) { ownerChanged(o.name, o.pid) }
            }
        }
    }
    p.terminationHandler = { _ in
        DispatchQueue.main.asyncAfter(deadline: .now() + 10) { log("owner watch ended, restarting it"); startOwnerStream() }
    }
    do { try p.run(); ownerStream = p } catch {
        log("owner watch cannot start: \(error)"); setHealth("the button watchdog cannot read the system log")
    }
}
startOwnerStream()
// This process is a new Now Playing client, so its first assert is a change of owner and the
// stream normally reports it. If it started too late to see it, read the last change from the log.
DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
    guard !ownerSeen else { return }
    let p = Process(), pipe = Pipe()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/log")
    p.arguments = ["show", "--last", "2m", "--style", "compact", "--predicate", ownerPredicate]
    p.standardOutput = pipe; p.standardError = FileHandle.nullDevice
    p.terminationHandler = { _ in
        let text = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        DispatchQueue.main.async {
            guard !ownerSeen else { return }
            if let o = text.split(separator: "\n").reversed().lazy.compactMap({ parseOwner(String($0)) }).first {
                ownerChanged(o.name, o.pid)
            } else { log("owner watch: no change of owner on record yet") }
        }
    }
    do { try p.run() } catch { log("owner history cannot be read: \(error)") }
}
atexit { ownerStream?.terminate() }
for sig in [SIGTERM, SIGINT] {
    signal(sig, SIG_IGN)
    let src = DispatchSource.makeSignalSource(signal: sig, queue: .main)
    src.setEventHandler { ownerStream?.terminate(); exit(0) }
    src.resume()
    signalSources.append(src)
}

assertNowPlaying()
settleSoon()
log("EarbudButtons started, gestures -> \(gestureScript)\(restPaused ? ", resting in paused" : "")")
app.run()
