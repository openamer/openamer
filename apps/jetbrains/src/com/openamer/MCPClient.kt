package com.openamer

import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.util.concurrent.CompletableFuture
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/**
 * JSON-RPC client that communicates with the OpenAmer MCP server over stdio.
 *
 * Spawns a child process via [ProcessBuilder], sends JSON-RPC 2.0 requests
 * over stdin, and reads responses from stdout via a daemon reader thread.
 * Supports request/response correlation via a pending-requests map with a
 * configurable timeout (default 30 seconds).
 */
class MCPClient(private val requestTimeoutMs: Long = 30_000) {

    private val gson: Gson = GsonBuilder().create()
    private val pendingRequests = ConcurrentHashMap<String, CompletableFuture<JsonObject>>()
    private val idCounter = AtomicInteger(0)
    private val running = AtomicBoolean(false)

    private var process: Process? = null
    private var writer: OutputStreamWriter? = null
    private var readerThread: Thread? = null

    /**
     * MCP tool definition returned by listTools().
     */
    data class MCPTool(
        val name: String,
        val description: String = "",
        val inputSchema: JsonObject? = null
    )

    /**
     * Starts the MCP server subprocess with the given command arguments.
     *
     * @param commands The command and its arguments, e.g. ["openamer", "mcp"]
     * @throws IllegalStateException if already connected
     * @throws Exception if the process cannot be started
     */
    @Synchronized
    fun connect(commands: List<String>) {
        if (running.get()) {
            throw IllegalStateException("MCPClient is already connected")
        }

        val pb = ProcessBuilder(commands)
            .redirectErrorStream(false)

        // Preserve the user's PATH and environment
        pb.environment()?.putAll(System.getenv())

        process = pb.start()
        writer = OutputStreamWriter(process!!.outputStream, "UTF-8")
        running.set(true)

        // Daemon reader thread: reads JSON-RPC responses from stdout
        val reader = BufferedReader(InputStreamReader(process!!.inputStream, "UTF-8"))
        readerThread = Thread({
            try {
                var line: String?
                while (running.get() && reader.readLine().also { line = it } != null) {
                    handleResponse(line!!)
                }
            } catch (ex: Exception) {
                if (running.get()) {
                    // Only log if we didn't initiate the disconnect
                    System.err.println("MCP reader error: ${ex.message}")
                }
            } finally {
                reader.close()
            }
        }, "mcp-reader").apply {
            isDaemon = true
            start()
        }

        // Drain stderr to a daemon thread to avoid blocking
        val errorReader = BufferedReader(InputStreamReader(process!!.errorStream, "UTF-8"))
        Thread({
            try {
                var line: String?
                while (errorReader.readLine().also { line = it } != null) {
                    System.err.println("[MCP] $line")
                }
            } catch (_: Exception) {
                // Silently drain on shutdown
            } finally {
                errorReader.close()
            }
        }, "mcp-stderr").apply {
            isDaemon = true
            start()
        }
    }

    /**
     * Sends a JSON-RPC 2.0 request to the MCP server and waits for the response.
     *
     * @param method The RPC method name
     * @param params Optional parameters as a JSON element
     * @return The "result" object from the response, or null on timeout/error
     */
    fun request(method: String, params: JsonElement? = null): JsonObject? {
        if (!running.get()) {
            throw IllegalStateException("MCPClient is not connected. Call connect() first.")
        }

        val id = idCounter.incrementAndGet().toString()
        val future = CompletableFuture<JsonObject>()
        pendingRequests[id] = future

        val request = JsonObject().apply {
            addProperty("jsonrpc", "2.0")
            addProperty("id", id.toInt())
            addProperty("method", method)
            if (params != null) {
                add("params", params)
            }
        }

        try {
            val requestStr = gson.toJson(request) + "\n"
            synchronized(this) {
                writer?.write(requestStr)
                writer?.flush()
            }

            // Wait for the response with timeout
            return future.get(requestTimeoutMs, TimeUnit.MILLISECONDS)
        } catch (ex: Exception) {
            pendingRequests.remove(id)
            System.err.println("MCP request '$method' failed: ${ex.message}")
            return null
        }
    }

    /**
     * Sends a chat message to the MCP server.
     * Convenience wrapper around [request].
     *
     * @param message The user's chat message
     * @return The response object with a "content" field
     */
    fun chat(message: String): JsonObject? {
        val params = JsonObject().apply {
            addProperty("message", message)
        }
        return request("chat", params)
    }

    /**
     * Lists available MCP tools from the server.
     * Convenience wrapper around [request].
     *
     * @return List of available tools, or empty list on failure
     */
    fun listTools(): List<MCPTool>? {
        val result = request("list_tools") ?: return null

        val toolsArray = result.getAsJsonArray("tools") ?: return emptyList()

        return toolsArray.map { element ->
            val obj = element.asJsonObject
            MCPTool(
                name = obj.get("name")?.asString ?: "",
                description = obj.get("description")?.asString ?: "",
                inputSchema = obj.get("inputSchema")?.asJsonObject
            )
        }
    }

    /**
     * Disconnects from the MCP server and cleans up resources.
     * Kills the subprocess if it is still running.
     */
    @Synchronized
    fun disconnect() {
        running.set(false)
        writer?.close()
        writer = null

        process?.let { proc ->
            proc.destroyForcibly()
            proc.waitFor(5, TimeUnit.SECONDS)
        }
        process = null

        // Fail all pending requests
        val ex = java.util.concurrent.CancellationException("MCP client disconnected")
        pendingRequests.forEach { (_, future) ->
            future.completeExceptionally(ex)
        }
        pendingRequests.clear()
    }

    /**
     * Returns whether the client is currently connected.
     */
    fun isConnected(): Boolean = running.get()

    // ---- Internal ----

    /**
     * Parses a JSON-RPC response line and dispatches it to the pending future.
     */
    private fun handleResponse(line: String) {
        try {
            val json = gson.fromJson(line, JsonObject::class.java)
            if (json == null) return

            // Check for JSON-RPC error
            val errorObj = json.get("error")
            if (errorObj != null && !errorObj.isJsonNull) {
                val errMsg = errorObj.asJsonObject?.get("message")?.asString ?: "Unknown error"
                val idElement = json.get("id")

                // Try to match to a pending request
                val id = when {
                    idElement != null && !idElement.isJsonNull -> idElement.asString
                    else -> null
                }

                if (id != null) {
                    val future = pendingRequests.remove(id)
                    future?.completeExceptionally(RuntimeException("MCP error: $errMsg"))
                }
                return
            }

            // Normal result
            val idElement = json.get("id")
            val resultElement = json.get("result")
            val id = when {
                idElement != null && !idElement.isJsonNull -> idElement.asString
                else -> return
            }

            val future = pendingRequests.remove(id)
            if (future != null && resultElement != null && !resultElement.isJsonNull) {
                future.complete(resultElement.asJsonObject)
            } else if (future != null) {
                // Empty result — complete with empty object
                future.complete(JsonObject())
            }
        } catch (ex: Exception) {
            System.err.println("MCP response parse error: ${ex.message}")
        }
    }
}