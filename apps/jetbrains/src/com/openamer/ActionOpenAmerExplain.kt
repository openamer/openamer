package com.openamer

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.vfs.VirtualFile

/**
 * Right-click a file → "Ask OpenAmer to explain this".
 *
 * Sends the full file content to the OpenAmer MCP server with an
 * "Explain this code" prompt and opens the chat tool window to show
 * the response.
 */
class ActionOpenAmerExplain : AnAction(), DumbAware {

    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val file: VirtualFile? = e.getData(CommonDataKeys.VIRTUAL_FILE)
        if (file == null || file.isDirectory) return

        val text = file.loadTextOrNull()
        if (text == null || text.isEmpty()) {
            OpenAmerNotifications.warn(project, "File is empty or binary.")
            return
        }

        val language = file.extension?.takeIf { it.isNotBlank() } ?: "text"

        val prompt = buildString {
            appendLine("Explain this code:")
            appendLine()
            appendLine("```$language")
            append(text.take(8000))
            appendLine()
            appendLine("```")
        }

        OpenAmerToolWindowChat.submitMessage(project, prompt)
    }

    override fun update(e: AnActionEvent) {
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE)
        e.presentation.isEnabledAndVisible = file != null && !file.isDirectory
    }

    /** Read the file text content, returning null for binary or oversized files. */
    private fun VirtualFile.loadTextOrNull(): String? {
        return try {
            if (length > 200_000) null // too large
            else String(contentsToByteArray(), charset)
        } catch (_: Exception) {
            null
        }
    }
}