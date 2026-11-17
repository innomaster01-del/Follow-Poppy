package app.followpoppy

import android.content.Context
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
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameMillis
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val Pink = Color(0xFFFF7FBF)
private val Blue = Color(0xFF5FB3FF)
private val SplashNight = Color(0xFF070B14)

private fun Context.png(name: String): ImageBitmap? =
    runCatching { assets.open(name).use { BitmapFactory.decodeStream(it) }?.asImageBitmap() }.getOrNull()

/**
 * The opening: on the night background, Poppy's paw prints walk up the screen (pink and blue, left and right, each one
 * popping in, the older ones fading behind) and lead into the ring the logo stands on; the logo pops up dim and lights
 * up (it brightens, its glow swells, a shine runs across it), then the name rises. About 3.3 s; a tap skips it.
 */
@Composable
internal fun Splash(w: Words, onDone: () -> Unit) {
    val context = LocalContext.current
    val logo by androidx.compose.runtime.produceState<ImageBitmap?>(null) {
        value = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) { context.png("splash_logo.png") }
    }
    val glow = remember { Animatable(0f) }
    val steps = remember { List(STEPS) { Animatable(0f) } }
    val logoIn = remember { Animatable(0f) }
    val light = remember { Animatable(0f) }
    val title = remember { Animatable(0f) }
    val out = remember { Animatable(1f) }
    var started by remember { mutableStateOf(false) }
    var done by remember { mutableStateOf(false) }
    fun finish() { if (!done) { done = true; onDone() } }
    LaunchedEffect(logo) {
        if (logo == null || started) return@LaunchedEffect                  // starts when the logo is ready
        started = true
        coroutineScope {
            launch { glow.animateTo(1f, tween(1000, easing = FastOutSlowInEasing)) }
            steps.forEachIndexed { i, a -> launch { delay(150L + i * 125L); a.animateTo(1f, spring(dampingRatio = 0.55f, stiffness = Spring.StiffnessMedium)) } }
            val after = 150L + STEPS * 125L
            launch { delay(after); logoIn.animateTo(1f, spring(dampingRatio = 0.5f, stiffness = Spring.StiffnessMediumLow)) }
            launch { delay(after + 380); light.animateTo(1f, tween(800, easing = FastOutSlowInEasing)) }
            launch { delay(after + 520); title.animateTo(1f, tween(600, easing = FastOutSlowInEasing)) }
        }
        delay(500)
        out.animateTo(0f, tween(300, easing = LinearEasing))
        finish()
    }
    Box(
        Modifier.fillMaxSize().graphicsLayer { alpha = out.value }.background(SplashNight)
            .clickable(remember { MutableInteractionSource() }, null) { finish() },
    ) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val dens = androidx.compose.ui.platform.LocalDensity.current.density
            val wpx = constraints.maxWidth.toFloat(); val hpx = constraints.maxHeight.toFloat()
            val lw = minOf(wpx * 0.72f, 300f * dens)                              // the logo's box (px)
            val lg = logo
            val lh = if (lg != null) lw * lg.height / lg.width else lw
            val lx = (wpx - lw) / 2; val ly = hpx * 0.40f - lh / 2
            // the logo's ring (its foot) in its picture: where the steps arrive
            val ring = Offset(lx + lw * 0.37f, ly + lh * 0.93f)
            Canvas(Modifier.fillMaxSize()) {
                drawCircle(Brush.radialGradient(listOf(Pink.copy(alpha = 0.22f * glow.value), Color.Transparent), Offset(size.width * 0.25f, size.height * 0.45f), size.width * 0.75f), size.width, Offset(size.width * 0.25f, size.height * 0.45f))
                drawCircle(Brush.radialGradient(listOf(Blue.copy(alpha = 0.26f * glow.value), Color.Transparent), Offset(size.width * 0.75f, size.height * 0.6f), size.width * 0.75f), size.width, Offset(size.width * 0.75f, size.height * 0.6f))
                // the steps: up a gentle S from the bottom edge to the ring
                fun path(t: Float): Offset {
                    val x = size.width * 0.5f + (ring.x - size.width * 0.5f) * t + size.width * 0.16f * kotlin.math.sin(t * Math.PI * 1.6).toFloat() * (1 - t)
                    val y = size.height * 1.02f + (ring.y + size.width * 0.06f - size.height * 1.02f) * t
                    return Offset(x, y)
                }
                val newest = steps.indexOfLast { it.value > 0.01f }
                steps.forEachIndexed { i, a ->
                    val v = a.value; if (v <= 0.01f) return@forEachIndexed
                    val t = (i + 0.5f) / STEPS
                    val p = path(t); val q = path(t + 0.01f)
                    val ang = Math.toDegrees(kotlin.math.atan2((q.y - p.y).toDouble(), (q.x - p.x).toDouble())).toFloat()
                    val side = if (i % 2 == 0) -1f else 1f
                    val nx = -(q.y - p.y); val ny = q.x - p.x; val nl = kotlin.math.hypot(nx, ny).coerceAtLeast(1e-3f)
                    val c = p + Offset(nx / nl, ny / nl) * (side * size.width * 0.028f)
                    val age = (newest - i).coerceAtLeast(0)
                    val fade = (1f - age * 0.09f).coerceIn(0.35f, 1f) * (1f - 0.4f * logoIn.value)
                    val sz = size.width * (0.030f + 0.010f * t) * (0.5f + 0.5f * v)
                    paw(c, ang, sz, (if (i % 2 == 0) Pink else Blue).copy(alpha = (v.coerceIn(0f, 1f) * fade)))
                }
            }
            // the logo: pops up dim, then lights up (brightens, its glow swells, a shine runs across it)
            if (lg != null) {
                val l = light.value
                Box(Modifier.offset { androidx.compose.ui.unit.IntOffset(lx.toInt(), ly.toInt()) }.size((lw / dens).dp, (lh / dens).dp).graphicsLayer {
                    val k = logoIn.value; scaleX = 0.25f + 0.75f * k; scaleY = 0.25f + 0.75f * k; alpha = k.coerceIn(0f, 1f)
                    transformOrigin = androidx.compose.ui.graphics.TransformOrigin(0.37f, 0.93f)   // grows out of the ring the steps lead to
                }, contentAlignment = Alignment.Center) {
                    Canvas(Modifier.fillMaxSize().graphicsLayer { scaleX = 1.4f; scaleY = 1.4f }) {
                        val g = kotlin.math.sin(l * Math.PI).toFloat() * 0.5f + l * 0.25f
                        drawCircle(Brush.radialGradient(listOf(Blue.copy(alpha = 0.4f * g), Pink.copy(alpha = 0.16f * g), Color.Transparent)), size.minDimension / 2)
                    }
                    val b = 0.4f + 0.6f * l
                    Box(Modifier.fillMaxSize().graphicsLayer { compositingStrategy = androidx.compose.ui.graphics.CompositingStrategy.Offscreen }) {
                        Image(lg, null, Modifier.fillMaxSize(), colorFilter = androidx.compose.ui.graphics.ColorFilter.colorMatrix(
                            androidx.compose.ui.graphics.ColorMatrix(floatArrayOf(b, 0f, 0f, 0f, 0f, 0f, b, 0f, 0f, 0f, 0f, 0f, b, 0f, 0f, 0f, 0f, 0f, 1f, 0f))))
                        Canvas(Modifier.fillMaxSize()) {
                            if (l > 0f && l < 1f) {
                                val x = -size.width * 0.5f + size.width * 2f * l
                                drawRect(Brush.linearGradient(listOf(Color.Transparent, Color.White.copy(alpha = 0.6f), Color.Transparent),
                                    Offset(x - size.width * 0.18f, 0f), Offset(x + size.width * 0.18f, size.height * 0.5f)), blendMode = androidx.compose.ui.graphics.BlendMode.SrcAtop)
                            }
                        }
                    }
                }
            }
            Column(Modifier.offset { androidx.compose.ui.unit.IntOffset(0, (ly + lh + 18 * dens).toInt()) }.fillMaxWidth()
                .graphicsLayer { alpha = title.value; translationY = (1 - title.value) * 14.dp.toPx() },
                horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Follow Poppy", color = Color.White, fontSize = 36.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.8).sp)
                Spacer(Modifier.height(6.dp))
                Text(w.t("פופי תוביל אותך לשם", "Poppy will lead the way"), color = Color.White.copy(alpha = 0.62f), fontSize = 16.sp)
            }
        }
    }
}

private const val STEPS = 10

private fun DrawScope.paw(c: Offset, angle: Float, s: Float, color: Color) {
    rotate(angle + 90f, c) {
        drawOval(color, Offset(c.x - s * 0.55f, c.y - s * 0.2f), Size(s * 1.1f, s * 0.85f))
        for ((dx, dy) in listOf(-0.5f to -0.55f, 0f to -0.8f, 0.5f to -0.55f)) drawCircle(color, s * 0.24f, Offset(c.x + dx * s, c.y + dy * s))
    }
}
