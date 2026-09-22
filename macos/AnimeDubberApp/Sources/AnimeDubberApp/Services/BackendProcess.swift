import Foundation

enum BackendProcessError: LocalizedError {
    case repositoryNotFound
    case processNotRunning
    case invalidRequest

    var errorDescription: String? {
        switch self {
        case .repositoryNotFound:
            "Could not locate the AnimeDubber repository. Set ANIMEDUBBER_REPO_ROOT while developing."
        case .processNotRunning:
            "The Python backend is not running."
        case .invalidRequest:
            "The backend request could not be encoded."
        }
    }
}

final class BackendProcess {
    private var process: Process?
    private var stdinPipe: Pipe?
    private var stdoutPipe: Pipe?
    private var stderrPipe: Pipe?
    private var stdoutBuffer = Data()
    private let writeLock = NSLock()

    private var onMessage: (([String: Any]) -> Void)?
    private var onDiagnostic: ((String) -> Void)?
    private var onTermination: ((Int32) -> Void)?

    func start(
        onMessage: @escaping ([String: Any]) -> Void,
        onDiagnostic: @escaping (String) -> Void,
        onTermination: @escaping (Int32) -> Void
    ) throws {
        if process?.isRunning == true { return }

        self.onMessage = onMessage
        self.onDiagnostic = onDiagnostic
        self.onTermination = onTermination

        guard let repoRoot = locateRepositoryRoot() else {
            throw BackendProcessError.repositoryNotFound
        }

        let process = Process()
        let input = Pipe()
        let output = Pipe()
        let error = Pipe()

        let venvPython = repoRoot.appendingPathComponent(".venv/bin/python")
        if FileManager.default.isExecutableFile(atPath: venvPython.path) {
            process.executableURL = venvPython
            process.arguments = ["-m", "anime_dubber.transport.stdio_server"]
        } else {
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = ["python3", "-m", "anime_dubber.transport.stdio_server"]
        }

        process.currentDirectoryURL = repoRoot
        process.standardInput = input
        process.standardOutput = output
        process.standardError = error

        output.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            self?.consumeStdout(data)
        }

        error.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            self?.onDiagnostic?(text)
        }

        process.terminationHandler = { [weak self] process in
            self?.onTermination?(process.terminationStatus)
        }

        try process.run()

        self.process = process
        self.stdinPipe = input
        self.stdoutPipe = output
        self.stderrPipe = error
    }

    @discardableResult
    func send(method: String, params: [String: Any] = [:], id: String = UUID().uuidString) throws -> String {
        guard process?.isRunning == true, let input = stdinPipe else {
            throw BackendProcessError.processNotRunning
        }

        let request: [String: Any] = [
            "type": "request",
            "id": id,
            "method": method,
            "params": params,
        ]

        guard JSONSerialization.isValidJSONObject(request),
              var data = try? JSONSerialization.data(withJSONObject: request) else {
            throw BackendProcessError.invalidRequest
        }
        data.append(0x0A)

        writeLock.lock()
        defer { writeLock.unlock() }
        try input.fileHandleForWriting.write(contentsOf: data)
        return id
    }

    func stop() {
        if process?.isRunning == true {
            _ = try? send(method: "shutdown", id: "shutdown")
            DispatchQueue.global().asyncAfter(deadline: .now() + 0.5) { [weak self] in
                guard let process = self?.process, process.isRunning else { return }
                process.terminate()
            }
        }
    }

    private func consumeStdout(_ data: Data) {
        stdoutBuffer.append(data)

        while let newline = stdoutBuffer.firstIndex(of: 0x0A) {
            let lineData = stdoutBuffer.prefix(upTo: newline)
            stdoutBuffer.removeSubrange(...newline)

            guard !lineData.isEmpty,
                  let object = try? JSONSerialization.jsonObject(with: Data(lineData)),
                  let dictionary = object as? [String: Any] else {
                continue
            }
            onMessage?(dictionary)
        }
    }

    private func locateRepositoryRoot() -> URL? {
        let env = ProcessInfo.processInfo.environment
        if let explicit = env["ANIMEDUBBER_REPO_ROOT"], !explicit.isEmpty {
            let url = URL(fileURLWithPath: explicit, isDirectory: true)
            if FileManager.default.fileExists(atPath: url.appendingPathComponent("anime_dubber").path) {
                return url
            }
        }

        var candidate = URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true)
        for _ in 0..<8 {
            if FileManager.default.fileExists(atPath: candidate.appendingPathComponent("anime_dubber").path) {
                return candidate
            }
            let parent = candidate.deletingLastPathComponent()
            if parent.path == candidate.path { break }
            candidate = parent
        }

        return nil
    }
}
