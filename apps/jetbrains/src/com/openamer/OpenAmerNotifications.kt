package com.openamer

import com.intellij.notification.NotificationGroupManager
import com.intellij.notification.NotificationType
import com.intellij.openapi.project.Project

/**
 * Helper for showing notifications to the user via the IDE's notification
 * system.
 */
object OpenAmerNotifications {

    private const val GROUP_ID = "OpenAmer Agent"

    fun warn(project: Project?, message: String) {
        show(project, NotificationType.WARNING, message)
    }

    fun info(project: Project?, message: String) {
        show(project, NotificationType.INFORMATION, message)
    }

    fun error(project: Project?, message: String) {
        show(project, NotificationType.ERROR, message)
    }

    private fun show(project: Project?, type: NotificationType, message: String) {
        NotificationGroupManager.getInstance()
            .getNotificationGroup(GROUP_ID)
            .createNotification(message, type)
            .notify(project)
    }
}