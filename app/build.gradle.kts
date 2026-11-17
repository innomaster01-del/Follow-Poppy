plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "app.followpoppy"
    compileSdk = 37
    defaultConfig {
        applicationId = "app.followpoppy"
        minSdk = 26
        targetSdk = 36
        versionCode = 9
        versionName = "1.8"
        // Mapbox public token (walking routes, search, map images) and an optional Google Cloud key with the ARCore API
        // (Street View VPS for metre-level accuracy): both from the repo secrets, never in the source
        buildConfigField("String", "MAPBOX_TOKEN", "\"${System.getenv("MAPBOX_TOKEN") ?: ""}\"")
        val geo = System.getenv("GOOGLE_AR_KEY") ?: ""
        buildConfigField("String", "AR_GEO_KEY", "\"$geo\""); manifestPlaceholders["arGeoKey"] = geo
        resValue("string", "app_name", "Follow Poppy")
    }
    // a fixed sideload key, so a new APK installs over the old one (not a Play Store key)
    signingConfigs {
        create("sideload") { storeFile = file("followpoppy-sideload.jks"); storePassword = "followpoppy"; keyAlias = "poppy"; keyPassword = "followpoppy" }
    }
    buildTypes {
        release {
            ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("sideload")
        }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_21; targetCompatibility = JavaVersion.VERSION_21 }
    buildFeatures { compose = true; buildConfig = true; resValues = true }
    androidResources { noCompress += listOf("glb") }
    testOptions { unitTests.isReturnDefaultValues = true }
    packaging { resources { excludes += "/META-INF/{AL2.0,LGPL2.1}" } }
}

kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_21) } }

dependencies {
    implementation("io.github.sceneview:arsceneview:4.60.0")
    implementation(platform("androidx.compose:compose-bom:2026.09.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.13.0")
    // ARCore Geospatial (Street View VPS, terrain, the street model) needs the Fused Location Provider in the app
    implementation("com.google.android.gms:play-services-location:21.3.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")   // the real org.json for JVM tests (android.jar only has stubs)
}
