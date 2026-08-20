import org.jetbrains.intellij.platform.gradle.IntelliJPlatformType
import org.jetbrains.intellij.platform.gradle.models.ProductRelease

plugins {
    id("org.jetbrains.intellij.platform.gradle") version "2.2.1"
    kotlin("jvm") version "2.1.0"
    id("java")
}

group = "com.openamer"
version = "0.1.0"

repositories {
    mavenCentral()
    intellijPlatform {
        defaultRepositories()
    }
}

dependencies {
    intellijPlatform {
        intellijIdeaCommunity("2024.3")
        instrumentationTools()
        pluginVerifier()
        zipSigner()
    }

    // JCEF (Chromium Embedded Framework) for the chat webview
    implementation("org.jetbrains.jcef:jcef:1.0.0")

    // kotlinx.coroutines for async MCP communication
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-swing:1.9.0")

    // JSON serialization for MCP JSON-RPC messages
    implementation("com.google.code.gson:gson:2.11.0")

    testImplementation(kotlin("test"))
    testImplementation("org.jetbrains.kotlin:kotlin-test-junit5:2.1.0")
}

intellijPlatform {
    pluginConfiguration {
        id = "com.openamer.jetbrains"
        name = "OpenAmer Agent"
        version = project.version as String
        description = """
            AI-powered code assistance via the OpenAmer Agent.
            <ul>
                <li><b>Chat</b> — Ctrl+Shift+A to open the OpenAmer Chat sidebar</li>
                <li><b>Explain</b> — Right-click any file → Ask OpenAmer to explain it</li>
                <li><b>Fix</b> — Select code, right-click → Ask OpenAmer to fix it</li>
            </ul>
            Connects to the OpenAmer MCP server running on your machine.
        """.trimIndent()
        vendor {
            name = "OpenAmer"
            email = "support@openamer.com"
            url = "https://openamer.com"
        }
    }

    instrumentCode = false
    signing {
        certificateChain = ""
        privateKey = ""
        password = ""
    }
}

kotlin {
    jvmToolchain(21)
}

tasks {
    runIde {
        // Auto-run `openamer mcp` in the background when starting the IDE
        jvmArgs("-Dopenamer.mcp.autoConnect=true")
    }

    test {
        useJUnitPlatform()
    }
}