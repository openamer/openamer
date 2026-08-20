package com.openamer

import com.intellij.openapi.diagnostic.Logger
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger

/**
 * MCP (Model Context Protocol) client that spawns `openamer mcp` as a
 * subprocess via [java.lang.ProcessBuilder] and communicates over stdio
 * using JSON-RPC 2.0.
 *
 * Usage:
 * ```
 * val client = MCPClient()
 * if (client.connect(listOf("openamer", "mcp"))) {
 *     val response = client.chat("Explain this code")
 *     client.disconnect()
 * }
 * ```
 */
class MCPClient {

    private val log = Logger.getInstance(MCPClient::class.java)
    private var process: Process? = null
    private var reader: BufferedReader? = null
    private var writer: java.io.OutputStream? = null
    private var readerThread: Thread? = null

    private val pending = ConcurrentHashMap<Int, PendingRequest>()
    private val reqId = AtomicInteger(0)

    /** Whether the MCP subprocess is alive and the JSON-RPC handshake completed. */
    @Volatile
    var isConnected: Boolean = false
        private set

    /**
     * Spawn `openamer mcp` and run the JSON-RPC initialize handshake.
     *
     * @param command Command tokens, e.g. `listOf("openamer", "mcp")`.
     * @return `true` if the connection and handshake succeeded.
     */
    fun connect(command: List<String>): Boolean {
        disconnect()

        return try {
            val pb = ProcessBuilder(command)
            pb.redirectErrorStream(false)
            pb.environment()["OPENAMER_MCP_CLIENT"] = "jetbrains"

            process = pb.start()
            writer = process!!.outputStream
            reader = BufferedReader(InputStreamReader(process!!.inputStream, "UTF-8"))

            // Start a daemon reader thread for JSON-RPC responses
            readerThread = Thread {
                try {
                    var line: String?
                    while (reader!!.readLine().also { line = it } != null) {
                        dispatchMessage(line!!)
                    }
                } catch (_: Exception) {
                    // Process terminated — nothing to do
                }
            }.apply {
                isDaemon = true
                name = "openamer-mcp-reader"
                start()
            }

            // Run the initialise handshake
            val result = request("initialize", mapOf(
                "protocolVersion" to "2024-11-05",
                "capabilities" to mapOf("tools" to emptyMap<String, String>()),
                "clientInfo" to mapOf(
                    "name" to "openamer-jetbrains",
                    "version" to "0.1.0"
                )
            ))

            notify("notifications/initialized")
            isConnected = true
            log.info("MCP connected to OpenAmer")
            true
        } catch (e: Exception) {
            log.warn("MCP connect failed: ${e.message}")
            disconnect()
            false
        }
    }

    /**
     * Kill the subprocess and reset state.
     */
    fun disconnect() {
        isConnected = false
        process?.let { p ->
            if (p.isAlive) {
                p.destroyForcibly()
            }
        }
        process = null
        reader = null
        writer = null
        readerThread = null
        pending.clear()
    }

    /**
     * Send a chat message to the OpenAmer MCP server and return the full
     * response text.
     */
    fun chat(message: String): String? {
        if (!isConnected) return null

        return try {
            val result = request("tools/call", mapOf(
                "name" to "openamer_chat",
                "arguments" to mapOf("message" to message)
            ))

            @Suppress("UNCHECKED_CAST")
            val content = (result as? Map<*, *>)
                ?.get("content") as? List<Map<String, Any>>
            content?.mapNotNull { c ->
                if (c["type"] == "text") c["text"] as? String else null
            }?.joinToString("") ?: "⚠️ No text content in response"
        } catch (e: Exception) {
            log.warn("MCP chat failed: ${e.message}")
            null
        }
    }

    /**
     * List the tools available on the MCP server.
     */
    fun listTools(): List<Map<String, Any>> {
        if (!isConnected) return emptyList()

        return try {
            val result = request("tools/list", null)
            @Suppress("UNCHECKED_CAST")
            (result as? Map<*, *>)?.get("tools") as? List<Map<String, Any>> ?: emptyList()
        } catch (e: Exception) {
            log.warn("MCP listTools failed: ${e.message}")
            emptyList()
        }
    }

    // ── JSON-RPC 2.0 internals ──────────────────────────────────────────── //

    private data class PendingRequest(
        val resolve: (Any?) -> Unit,
        val reject: (Exception) -> Unit,
    )

    /**
     * Send a JSON-RPC 2.0 request and block for the response (up to 30 s).
     */
    @Suppress("UNCHECKED_CAST")
    private fun request(method: String, params: Any?): Any? {
        val id = reqId.incrementAndGet()
        val msg = buildJsonRpc("2.0", id, method, params)

        return java.util.concurrent.CompletableFuture<Any?>().apply {
            pending[id] = PendingRequest(
                resolve = { complete(it) },
                reject = { completeExceptionally(it) }
            )

            writeMessage(msg)

            // Timeout after 30 seconds
            java.util.concurrent.CompletableFuture
                .delayedExecutor(30, java.util.concurrent.TimeUnit.SECONDS)
                .execute {
                    val p = pending.remove(id)
                    if (p != null) {
                        p.reject(java.util.concurrent.TimeoutException("MCP request timed out: $method"))
                    }
                }
        }.get()
    }

    /**
     * Send a JSON-RPC 2.0 notification (no response expected).
     */
    private fun notify(method: String, params: Any? = null) {
        val msg = buildJsonRpc("2.0", null, method, params)
        writeMessage(msg)
    }

    /**
     * Dispatch an incoming JSON line — either a response to a pending
     * request or a server notification.
     */
    private fun dispatchMessage(line: String) {
        try {
            @Suppress("UNCHECKED_CAST")
            val msg = com.intellij.openapi.util.text.StringUtil
                .unquoteString(line)
                .let { parseJson(it) as? Map<String, Any?> ?: return }

            val id = msg["id"] as? Int
            if (id != null && id in pending) {
                val p = pending.remove(id)
                if (p != null) {
                    if (msg.containsKey("error")) {
                        val err = msg["error"] as? Map<*, *>
                        val msgText = err?.get("message") as? String ?: "Unknown error"
                        p.reject(Exception(msgText))
                    } else {
                        p.resolve(msg["result"])
                    }
                }
            }
        } catch (_: Exception) {
            // Skip malformed JSON lines
        }
    }

    /**
     * Write a single JSON-RPC message as a newline-delimited JSON line.
     */
    private fun writeMessage(json: String) {
        try {
            writer?.write((json + "\n").toByteArray(Charsets.UTF_8))
            writer?.flush()
        } catch (e: Exception) {
            log.warn("MCP write failed: ${e.message}")
        }
    }

    /**
     * Build a JSON-RPC 2.0 message string.
     */
    private fun buildJsonRpc(
        jsonrpc: String,
        id: Int?,
        method: String,
        params: Any?,
    ): String {
        val sb = StringBuilder()
        sb.append("{\"jsonrpc\":\"$jsonrpc\"")
        if (id != null) sb.append(",\"id\":$id")
        sb.append(",\"method\":${jsonEncode(method)}")
        if (params != null) sb.append(",\"params\":${jsonEncode(params)}")
        sb.append("}")
        return sb.toString()
    }

    /**
     * Minimal JSON encoder for the primitives we need (strings, maps, lists).
     */
    private fun jsonEncode(value: Any?): String {
        return when (value) {
            null -> "null"
            is String -> "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""
            is Number -> value.toString()
            is Boolean -> value.toString()
            is Map<*, *> -> value.entries.joinToString(
                prefix = "{", postfix = "}"
            ) { (k, v) -> "${jsonEncode(k as? String ?: "")}:${jsonEncode(v)}" }
            is List<*> -> value.joinToString(
                prefix = "[", postfix = "]"
            ) { jsonEncode(it) }
            else -> "\"$value\""
        }
    }

    /**
     * Minimal parser for JSON-RPC message frames (assumes well-formed input).
     */
    private fun parseJson(text: String): Any? {
        // For production, use a real JSON library (Gson / kotlinx.serialization).
        // This stub returns a dummy map so the scaffold compiles.
        // MCPClientTest.kt should test the real JSON handling.
        return try {
            // Quick-and-dirty parse for our simple message shapes
            parseJsonObject(text)
        } catch (_: Exception) {
            null
        }
    }

    private fun parseJsonObject(text: String): Map<String, Any?>? {
        val trimmed = text.trim()
        if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return null
        val inner = trimmed.substring(1, trimmed.length - 1)

        val result = mutableMapOf<String, Any?>()
        var i = 0
        while (i < inner.length) {
            // Skip whitespace
            while (i < inner.length && inner[i] <= ' ') i++
            if (i >= inner.length) break
            if (inner[i] == ',') { i++; continue }

            // Parse key
            if (inner[i] != '"') return null
            val keyEnd = inner.indexOf('"', i + 1)
            if (keyEnd < 0) return null
            val key = inner.substring(i + 1, keyEnd)
            i = keyEnd + 1

            // Skip colon
            while (i < inner.length && inner[i] != ':') i++
            i++

            // Parse value (simplified)
            while (i < inner.length && inner[i] <= ' ') i++
            when {
                inner[i] == '"' -> {
                    val vEnd = inner.indexOf('"', i + 1)
                    if (vEnd >= 0) {
                        result[key] = inner.substring(i + 1, vEnd)
                        i = vEnd + 1
                    }
                }
                inner[i] == '{' -> {
                    // Nested object — skip to matching brace
                    var depth = 0
                    val start = i
                    while (i < inner.length) {
                        if (inner[i] == '{') depth++
                        if (inner[i] == '}') { depth--; if (depth == 0) break }
                        i++
                    }
                    result[key] = inner.substring(start, i + 1)
                    i++
                }
                inner[i] == '[' -> {
                    var depth = 0
                    val start = i
                    while (i < inner.length) {
                        if (inner[i] == '[') depth++
                        if (inner[i] == ']') { depth--; if (depth == 0) break }
                        i++
                    }
                    result[key] = inner.substring(start, i + 1)
                    i++
                }
                inner[i].isDigit() || inner[i] == '-' -> {
                    val numEnd = i + 1
                    while (numEnd < inner.length && (inner[numEnd].isDigit() || inner[numEnd] == '.')) {
                        // advance
                    }
                    result[key] = inner.substring(i, numEnd).toDoubleOrNull()?.toInt()
                        ?: inner.substring(i, numEnd).toDoubleOrNull()
                    i = numEnd
                }
                inner.startsWith("null", i) -> { result[key] = null; i += 4 }
                inner.startsWith("true", i) -> { result[key] = true; i += 4 }
                inner.startsWith("false", i) -> { result[key] = false; i += 5 }
            }
            // skip trailing comma
            while (i < inner.length && inner[i] == ',') i++
        }
        return result
    }
}