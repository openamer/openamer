package com.openamer

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.project.DumbAware

/**
 * Action to send the currently selected code to OpenAmer with a "fix" prompt.
 * Appears in the editor's right-click context menu.
 */
class ActionOpenAmerFix : AnAction(), DumbAware {

    override fun update(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR)
        val project = e.project
        e.presentation.isEnabledAndVisible =
            project != null && editor != null && editor.selectionModel.hasSelection()
    }

    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val editor = e.getData(CommonDataKeys.EDITOR) ?: return
        val selectedText = editor.selectionModel.selectedText ?: return
        val fileName = e.getData(CommonDataKeys.PSI_FILE)?.virtualFile?.name ?: "Unknown"

        val message = buildString {
            appendLine("Please fix the following code from `$fileName`:")
            appendLine("```")
            appendLine(selectedText)
            appendLine("```")
        }

        OpenAmerToolWindowFactory.openAndSend(project, message)
    }
}