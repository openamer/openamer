package com.openamer

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.wm.ToolWindowManager

/**
 * Action to open the OpenAmer Chat tool window.
 * Bound to Ctrl+Shift+A by default.
 */
class ActionOpenAmerChat : AnAction(), DumbAware {

    override fun update(e: AnActionEvent) {
        val project = e.project
        e.presentation.isEnabledAndVisible = project != null
    }

    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val toolWindow = ToolWindowManager.getInstance(project)
            .getToolWindow("OpenAmerChat") ?: return
        toolWindow.activate(null, true)
    }
}