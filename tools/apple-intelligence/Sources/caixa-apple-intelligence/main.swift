// caixa-apple-intelligence: Apple's on-device model (Foundation Models) for Caixa.
//
//   caixa-apple-intelligence --check
//       prints {"ready":true}, or {"ready":false,"reason":…,"message":…}
//       (reason: not_eligible, not_enabled, not_ready, unavailable)
//   caixa-apple-intelligence
//       reads one request per line:  {"id":1,"instructions":"…","prompt":"…","temperature":0.2}
//       writes one answer per line:  {"id":1,"text":"…"}
//                                or  {"id":1,"error":"…","refused":true|false}
//
// Each request gets a session of its own (nothing is remembered between requests). Caixa runs
// several of these programs at once and gives each one request at a time.

import Foundation
import FoundationModels

struct Request: Decodable {
    let id: Int
    let instructions: String
    let prompt: String
    let temperature: Double?
}

struct Answer: Encodable, Sendable {
    let id: Int
    var text: String? = nil
    var error: String? = nil
    var refused: Bool? = nil
}

struct Check: Encodable {
    let ready: Bool
    var reason: String? = nil
    var message: String? = nil
}

let encoder = JSONEncoder()

func emit<T: Encodable>(_ value: T) {
    guard let data = try? encoder.encode(value), let line = String(data: data, encoding: .utf8) else {
        return
    }
    print(line)
    fflush(stdout)
}

func availability() -> Check {
    switch SystemLanguageModel.default.availability {
    case .available:
        return Check(ready: true)
    case .unavailable(let reason):
        switch reason {
        case .deviceNotEligible:
            return Check(ready: false, reason: "not_eligible", message: "This Mac cannot run Apple Intelligence.")
        case .appleIntelligenceNotEnabled:
            return Check(ready: false, reason: "not_enabled", message: "Apple Intelligence is turned off.")
        case .modelNotReady:
            return Check(ready: false, reason: "not_ready", message: "The model is not ready yet.")
        @unknown default:
            return Check(ready: false, reason: "unavailable", message: String(describing: reason))
        }
    }
}

func answer(_ request: Request) async -> Answer {
    let instructions: String? = request.instructions.isEmpty ? nil : request.instructions
    let session = LanguageModelSession(instructions: instructions)
    let options = GenerationOptions(temperature: request.temperature ?? 0)
    do {
        let response = try await session.respond(to: request.prompt, options: options)
        return Answer(id: request.id, text: response.content)
    } catch let error as LanguageModelSession.GenerationError {
        switch error {
        case .guardrailViolation:
            return Answer(id: request.id, error: "declined by the safety filter", refused: true)
        default:
            return Answer(id: request.id, error: String(describing: error), refused: false)
        }
    } catch {
        return Answer(id: request.id, error: String(describing: error), refused: false)
    }
}

if CommandLine.arguments.dropFirst().first == "--check" {
    emit(availability())
    exit(0)
}

let decoder = JSONDecoder()
while let line = readLine() {
    if line.isEmpty { continue }
    guard let data = line.data(using: .utf8), let request = try? decoder.decode(Request.self, from: data) else {
        emit(Answer(id: 0, error: "not a request", refused: false))
        continue
    }
    emit(await answer(request))
}
