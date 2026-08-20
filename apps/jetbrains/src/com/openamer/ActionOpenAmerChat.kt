package com.openamer

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.wm.ToolWindowManager

/**
 * Ctrl+Shift+A → Opens the OpenAmer Chat tool window.
 *
 * Activates the "OpenAmerChat" tool window registered in plugin.xml
 * so the user can start a conversation with the OpenAmer agent.
 */
class ActionOpenAmerChat : AnAction(), DumbAware {

    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val toolWindow = ToolWindowManager.getInstance(project)
            .getToolWindow("OpenAmerChat") ?: return

        if (!toolWindow.isAvailable) toolWindow.isAvailable = true
        toolWindow.activate(null, true, true)
    }

    override fun update(e: AnActionEvent) {
        // Only enable when a project is open
        e.presentation.isEnabledAndVisible = e.project != null
    }
}