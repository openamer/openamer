package com.openamer

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.DumbAware

/**
 * Right-click a selection → "Ask OpenAmer to fix this".
 *
 * Sends the selected code to the OpenAmer MCP server with a
 * "Fix this code" prompt and opens the chat tool window.
 */
class ActionOpenAmerFix : AnAction(), DumbAware {

    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val editor: Editor? = e.getData(CommonDataKeys.EDITOR)
        if (editor == null) return

        val selectionModel = editor.selectionModel
        val selectedText = selectionModel.selectedText
        if (selectedText.isNullOrBlank()) {
            OpenAmerNotifications.warn(project, "No text selected.")
            return
        }

        val document = editor.document
        val language = document.getText(
            com.intellij.psi.LanguageUtil.getLanguageFileType(document)?.let {
                // Try to infer language from the file type
                it.name.lowercase()
            } ?: "text"
        )

        val prompt = buildString {
            appendLine("Fix this code:")
            appendLine()
            appendLine("```$language")
            append(selectedText.take(8000))
            appendLine()
            appendLine("```")
        }

        OpenAmerToolWindowChat.submitMessage(project, prompt)
    }

    override fun update(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR)
        val hasSelection = editor?.selectionModel?.hasSelection() == true
        e.presentation.isEnabledAndVisible = hasSelection
    }
}