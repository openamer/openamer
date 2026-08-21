plugins {
    id("org.jetbrains.intellij.platform.gradle") version "2.2.1"
    kotlin("jvm") version "2.1.0"
}

repositories {
    mavenCentral()
    intellijPlatform { defaultRepositories() }
}

dependencies {
    intellijPlatform { intellijIdeaCommunity("2024.3") }
    implementation("com.google.code.gson:gson:2.11.0")
}

intellijPlatform {
    pluginConfiguration {
        id = "com.openamer.jetbrains"
        name = "OpenAmer Agent"
        version = "0.1.0"
    }
}

kotlin { jvmToolchain(21) }