package com.openamer

import com.intellij.notification.Notification
import com.intellij.notification.NotificationAction
import com.intellij.notification.NotificationGroupManager
import com.intellij.notification.NotificationType
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindowManager

/**
 * Helper utilities for showing OpenAmer notifications in the IntelliJ IDE.
 *
 * Uses the "OpenAmer Agent" notification group registered in plugin.xml.
 */
object OpenAmerNotifications {

    private const val GROUP_ID = "OpenAmer Agent"

    /**
     * Shows a plain info notification.
     */
    fun info(project: Project?, title: String, content: String) {
        val notification = NotificationGroupManager.getInstance()
            .getNotificationGroup(GROUP_ID)
            .createNotification(content, NotificationType.INFORMATION)
            .setTitle(title)
        notification.notify(project)
    }

    /**
     * Shows a warning notification.
     */
    fun warn(project: Project?, title: String, content: String) {
        val notification = NotificationGroupManager.getInstance()
            .getNotificationGroup(GROUP_ID)
            .createNotification(content, NotificationType.WARNING)
            .setTitle(title)
        notification.notify(project)
    }

    /**
     * Shows an error notification.
     */
    fun error(project: Project?, title: String, content: String) {
        val notification = NotificationGroupManager.getInstance()
            .getNotificationGroup(GROUP_ID)
            .createNotification(content, NotificationType.ERROR)
            .setTitle(title)
        notification.notify(project)
    }

    /**
     * Shows an info notification with an action that opens the OpenAmer Chat panel.
     */
    fun infoWithOpenChat(project: Project?, title: String, content: String) {
        val notification = NotificationGroupManager.getInstance()
            .getNotificationGroup(GROUP_ID)
            .createNotification(content, NotificationType.INFORMATION)
            .setTitle(title)

        notification.addAction(object : NotificationAction("Open Chat") {
            override fun actionPerformed(e: AnActionEvent, notification: Notification) {
                val proj = e.project ?: project ?: return
                val toolWindow = ToolWindowManager.getInstance(proj)
                    .getToolWindow("OpenAmerChat")
                toolWindow?.activate(null, true)
                notification.expire()
            }
        })

        notification.notify(project)
    }

    /**
     * Shows an info notification about MCP connection status.
     */
    fun mcpConnectionStatus(project: Project?, connected: Boolean) {
        if (connected) {
            info(project, "MCP Connection", "OpenAmer MCP server connected successfully.")
        } else {
            warn(project, "MCP Connection", "OpenAmer MCP server disconnected. Chat is unavailable.")
        }
    }

    /**
     * Shows a notification with the result of an Explain/Fix action.
     */
    fun showActionResult(project: Project?, actionName: String, resultSummary: String) {
        infoWithOpenChat(project, "OpenAmer $actionName",
            "OpenAmer has processed your request:\n$resultSummary")
    }
}