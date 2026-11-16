package app.followpoppy

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val i = intent
        val smoke = i?.getBooleanExtra("smoke", false) == true          // CI smoke test on the ARCore emulator
        fun ll(k: String) = i?.getStringExtra(k)?.split(',')?.let { LatLng(it[0].toDouble(), it[1].toDouble()) }
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                if (i?.getBooleanExtra("walktest", false) == true) WalkTest()
                else WalkApp(smoke = smoke, testDest = ll("dest"), testFrom = ll("from"))
            }
        }
    }
}
