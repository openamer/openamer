plugins {
    id("org.jetbrains.intellij.platform") version "2.18.1"
    kotlin("jvm") version "2.1.0"
}

repositories {
    mavenCentral()
    intellijPlatform { defaultRepositories() }
}

dependencies {
    intellijPlatform {
        intellijIdeaCommunity("2024.3")
        instrumentationTools()
    }
    implementation("com.google.code.gson:gson:2.11.0")
}

intellijPlatform {
    pluginConfiguration {
        id = "com.openamer.jetbrains"
        name = "OpenAmer Agent"
        version = "0.1.0"
    }
}

kotlin {
    jvmToolchain(17)
}

tasks {
    buildSearchableOptions {
        enabled = false
    }
}