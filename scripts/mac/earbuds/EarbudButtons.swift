// EarbudButtons: background app that owns the Bluetooth headset buttons by registering as the
// macOS "Now Playing" app, and maps them to voice2clipboard gestures.
//   single press  -> "pause"         -> on_gesture.sh single
//   double press  -> "nextTrack"     -> on_gesture.sh double
//   triple press  -> "previousTrack" -> on_gesture.sh triple
// Long presses change volume on the headset itself and never reach the Mac as commands.
// While another app is playing audio, macOS routes the buttons to that app instead; this app
// takes them back when it next re-asserts its Now Playing state (at start, after each gesture,
// and when it receives SIGUSR1).
import AppKit
import MediaPlayer

let gestureScript = CommandLine.arguments.count > 1
    ? CommandLine.arguments[1]
    : "/Users/remi/voice2clipboard/scripts/mac/secretary/on_gesture.sh"
let logPath = "/Users/remi/voice2clipboard/runtime/secretary/earbuds.log"

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
    assertNowPlaying()
}

let center = MPRemoteCommandCenter.shared()
let mapping: [(MPRemoteCommand, String, String)] = [
    (center.pauseCommand, "pause", "single"),
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

signal(SIGUSR1, SIG_IGN)
let usr1 = DispatchSource.makeSignalSource(signal: SIGUSR1, queue: .main)
usr1.setEventHandler { log("SIGUSR1: re-asserting Now Playing"); assertNowPlaying() }
usr1.resume()

assertNowPlaying()
log("EarbudButtons started, gestures -> \(gestureScript)")
app.run()
