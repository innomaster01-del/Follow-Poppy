package app.followpoppy

import android.graphics.BitmapFactory
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * The opening screen: night sky lit softly in Poppy's colour, her paw prints walking up towards the middle one by one,
 * then Poppy herself pops in (a soft spring, one little hop), and the name rises under her. About 2.6 s; a tap skips it.
 */
@Composable
internal fun Splash(w: Words, poppy: String, onDone: () -> Unit) {
    val context = LocalContext.current
    val accent = if (poppy == "boy") Color(0xFF5FB3FF) else Color(0xFFFF7FBF)
    val img = remember(poppy) {
        runCatching { context.assets.open("splash_poppy_$poppy.png").use { BitmapFactory.decodeStream(it) }?.asImageBitmap() }.getOrNull()
    }
    val glow = remember { Animatable(0f) }
    val paws = remember { List(PAWS) { Animatable(0f) } }
    val pop = remember { Animatable(0f) }
    val hop = remember { Animatable(0f) }
    val title = remember { Animatable(0f) }
    val out = remember { Animatable(1f) }
    var done by remember { mutableStateOf(false) }
    fun finish() { if (!done) { done = true; onDone() } }

    LaunchedEffect(Unit) {
        coroutineScope {
            launch { glow.animateTo(1f, tween(900, easing = FastOutSlowInEasing)) }
            paws.forEachIndexed { i, a -> launch { delay(150L + i * 140L); a.animateTo(1f, tween(320, easing = FastOutSlowInEasing)) } }
            launch {
                delay(150L + PAWS * 140L)
                pop.animateTo(1f, spring(dampingRatio = 0.62f, stiffness = Spring.StiffnessLow))
            }
            launch {
                delay(150L + PAWS * 140L + 380)
                hop.animateTo(1f, tween(220, easing = FastOutSlowInEasing)); hop.animateTo(0f, spring(dampingRatio = 0.5f, stiffness = Spring.StiffnessMediumLow))
            }
            launch { delay(150L + PAWS * 140L + 260); title.animateTo(1f, tween(520, easing = FastOutSlowInEasing)) }
        }
        delay(450)
        out.animateTo(0f, tween(320, easing = LinearEasing))
        finish()
    }

    Box(
        Modifier.fillMaxSize().graphicsLayer { alpha = out.value }.background(SplashNight)
            .clickable(remember { MutableInteractionSource() }, null) { finish() },
        contentAlignment = Alignment.Center,
    ) {
        // the glow, and the paw prints coming up from the bottom towards Poppy (left, right, left …)
        Canvas(Modifier.fillMaxSize()) {
            val c = Offset(size.width / 2, size.height * 0.44f)
            drawCircle(Brush.radialGradient(listOf(accent.copy(alpha = 0.34f * glow.value), Color.Transparent), c, size.width * (0.35f + 0.35f * glow.value)), size.width * 0.8f, c)
            drawCircle(Brush.radialGradient(listOf(Color(0xFF22D3EE).copy(alpha = 0.10f * glow.value), Color.Transparent), Offset(size.width * 0.5f, size.height), size.width * 0.9f), size.width, Offset(size.width * 0.5f, size.height))
            val pw = size.width * 0.075f
            paws.forEachIndexed { i, a ->
                val t = a.value; if (t <= 0f) return@forEachIndexed
                val k = i.toFloat() / (PAWS - 1)
                val y = size.height * (0.95f - 0.27f * k); val x = size.width * 0.5f + (if (i % 2 == 0) -1 else 1) * size.width * 0.07f
                val fade = 1f - 0.55f * pop.value * (1 - k)                                       // the old prints dim as Poppy arrives
                rotate(if (i % 2 == 0) -8f else 8f, Offset(x, y)) {
                    val s = pw * (0.7f + 0.3f * t); val col = accent.copy(alpha = 0.85f * t * fade)
                    drawOval(col, Offset(x - s * 0.55f, y - s * 0.2f), Size(s * 1.1f, s * 0.85f))
                    for ((dx, dy) in listOf(-0.5f to -0.55f, 0f to -0.8f, 0.5f to -0.55f)) drawCircle(col, s * 0.24f, Offset(x + dx * s, y + dy * s))
                }
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(
                Modifier.size(210.dp).graphicsLayer {
                    val p = pop.value
                    scaleX = 0.4f + 0.6f * p; scaleY = 0.4f + 0.6f * p + 0.04f * hop.value; alpha = p.coerceIn(0f, 1f)
                    translationY = (1 - p) * 60.dp.toPx() - hop.value * 18.dp.toPx()
                },
                contentAlignment = Alignment.Center,
            ) {
                if (img != null) Image(img, null, Modifier.fillMaxSize())
                else Canvas(Modifier.fillMaxSize()) { miniPoppyIcon(accent) }
            }
            Spacer(Modifier.height(22.dp))
            Column(Modifier.graphicsLayer { alpha = title.value; translationY = (1 - title.value) * 14.dp.toPx() }, horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Follow Poppy", color = Color.White, fontSize = 34.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.7).sp)
                Spacer(Modifier.height(6.dp))
                Text(w.t("פופי תוביל אותך לשם", "Poppy will lead the way"), color = Color.White.copy(alpha = 0.62f), fontSize = 16.sp)
            }
        }
    }
}

private const val PAWS = 6
private val SplashNight = Color(0xFF070B14)
