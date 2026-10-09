// Scrollhjelper for BeatStep-scriptet.
//
// Live lar ikke scripts panorere eller scrolle arrangementet. Scriptet sender derfor "scroll <dx> <dy>"
// (piksler, dx > 0 = bildet flytter seg mot høyre, dy > 0 = nedover) som UDP til 127.0.0.1:9817, og dette
// programmet lager en scroll-hendelse, som om styreflaten ble brukt. Hendelsen går til vinduet under
// musepekeren, så pekeren må ligge over arrangementet.
//
// Bygg:  swiftc -O beatstep-scroll.swift -o beatstep-scroll
// Kjør:  ./beatstep-scroll   (må ha tilgang under Personvern og sikkerhet > Tilgjengelighet)
//
// Live-scriptet starter programmet selv, med --stopp-med-forelder: da avslutter det når Live er borte,
// også hvis Live krasjer.

import CoreGraphics
import Foundation

let port: UInt16 = 9817
let followParent = CommandLine.arguments.contains("--stopp-med-forelder")
let parent = getppid()
setvbuf(stdout, nil, _IOLBF, 0)

if !CGPreflightPostEventAccess() {
    print("Mangler tilgang til å sende hendelser. Gi programmet (eller terminalen det kjører i) tilgang under")
    print("Systeminnstillinger > Personvern og sikkerhet > Tilgjengelighet, og start det på nytt.")
    CGRequestPostEventAccess()
}

let fd = socket(AF_INET, SOCK_DGRAM, 0)
var address = sockaddr_in()
address.sin_family = sa_family_t(AF_INET)
address.sin_port = port.bigEndian
address.sin_addr.s_addr = inet_addr("127.0.0.1")
let bound = withUnsafePointer(to: &address) {
    $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) }
}
if bound != 0 {
    print("Port \(port) er opptatt. Kjører scrollhjelperen allerede?")
    exit(1)
}
print("Scrollhjelperen lytter på 127.0.0.1:\(port)")

// recv gir opp annethvert sekund, så programmet får sjekket om forelderen lever.
var timeout = timeval(tv_sec: 2, tv_usec: 0)
setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout<timeval>.size))

var buffer = [UInt8](repeating: 0, count: 256)
while true {
    let length = recv(fd, &buffer, buffer.count, 0)
    if length <= 0 {
        if followParent && getppid() != parent { exit(0) }
        continue
    }
    let parts = String(decoding: buffer[0..<length], as: UTF8.self).split(separator: " ")
    guard parts.count == 3, parts[0] == "scroll", let dx = Int32(parts[1]), let dy = Int32(parts[2]) else {
        print("Ukjent melding")
        continue
    }
    // Hjulverdiene har motsatt fortegn: positivt hjul ruller innholdet ned og mot høyre, altså bildet opp og mot venstre.
    let event = CGEvent(scrollWheelEvent2Source: nil, units: .pixel, wheelCount: 2, wheel1: -dy, wheel2: -dx, wheel3: 0)
    event?.post(tap: .cghidEventTap)
    print("scroll dx=\(dx) dy=\(dy)\(CGPreflightPostEventAccess() ? "" : "  (mangler tilgang, ingenting skjer)")")
}
