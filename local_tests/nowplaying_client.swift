// Test helper for test_nowplaying_watchdog.sh: a silent Now Playing client (no audio, no
// permission) that stands in for "a browser tab with a video". Driven by stdin lines:
//   assert  = info + playbackState .playing (what EarbudButtons does today)
//   touch   = info only, elapsed time bumped (candidate passive probe)
//   state   = playbackState = .playing again, nothing else
//   claim   = .paused then .playing, plus info (candidate reclaim)
//   pause   = playbackState = .paused
//   quit
import AppKit
import MediaPlayer

let name = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "agent"
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let info = MPNowPlayingInfoCenter.default()
var elapsed = 0.0
func say(_ s: String) {
    let f = DateFormatter(); f.dateFormat = "HH:mm:ss.SSS"
    print("\(f.string(from: Date())) [\(name) \(getpid())] \(s)"); fflush(stdout)
}
func setInfo() {
    elapsed += 1
    info.nowPlayingInfo = [MPMediaItemPropertyTitle: "probe \(name)", MPMediaItemPropertyPlaybackDuration: 36000.0,
                           MPNowPlayingInfoPropertyElapsedPlaybackTime: elapsed, MPNowPlayingInfoPropertyPlaybackRate: 1.0]
}
let c = MPRemoteCommandCenter.shared()
for cmd in [c.playCommand, c.pauseCommand, c.togglePlayPauseCommand, c.nextTrackCommand, c.previousTrackCommand] {
    cmd.isEnabled = true
    cmd.addTarget { _ in say("GOT A COMMAND"); return .success }
}
DispatchQueue.global().async {
    while let line = readLine() {
        let cmd = line.trimmingCharacters(in: .whitespaces)
        DispatchQueue.main.sync {
            switch cmd {
            case "assert": setInfo(); info.playbackState = .playing
            case "touch": setInfo()
            case "state": info.playbackState = .playing
            case "claim": info.playbackState = .paused; setInfo(); info.playbackState = .playing
            case "pause": info.playbackState = .paused
            case "quit": say("quit"); exit(0)
            default: break
            }
            say(cmd)
        }
    }
    exit(0)
}
app.run()
