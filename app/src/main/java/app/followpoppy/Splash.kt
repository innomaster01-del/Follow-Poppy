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

/** The opening's pictures, decoded off the main thread (so the first frame is not held up). */
private class SplashArt(val girl: List<ImageBitmap?>, val boy: List<ImageBitmap?>, val logo: ImageBitmap?)

/**
 * The opening: both Poppys, small, walk in from the two sides (her walk loop, rendered from her 3D model) leaving paw
 * prints behind them, meet in the middle and hop together; then the app's logo pops up above them and lights up, and
 * the name rises. About 3.5 s; a tap skips it.
 */
@Composable
internal fun Splash(w: Words, onDone: () -> Unit) {
    val context = LocalContext.current
    val art by androidx.compose.runtime.produceState<SplashArt?>(null) {
        value = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
            SplashArt(List(8) { context.png("splash_girl_walk$it.png") }, List(8) { context.png("splash_boy_walk$it.png") }, context.png("splash_logo.png"))
        }
    }
    val logoIn = remember { Animatable(0f) }
    val light = remember { Animatable(0f) }
    val glow = remember { Animatable(0f) }
    val walk = remember { Animatable(0f) }                                  // 0 at the screen edges … 1 met in the middle
    val hop = remember { Animatable(0f) }
    val title = remember { Animatable(0f) }
    val out = remember { Animatable(1f) }
    var clock by remember { mutableIntStateOf(0) }
    var done by remember { mutableStateOf(false) }
    fun finish() { if (!done) { done = true; onDone() } }
    LaunchedEffect(Unit) { val t0 = withFrameMillis { it }; while (true) withFrameMillis { clock = (it - t0).toInt() } }
    LaunchedEffect(art) {
        if (art == null) return@LaunchedEffect                                  // starts when the pictures are ready
        coroutineScope {
            launch { glow.animateTo(1f, tween(900, easing = FastOutSlowInEasing)) }
            launch { delay(120); walk.animateTo(1f, tween(1500, easing = LinearEasing)) }
            launch { delay(1650); hop.animateTo(1f, tween(200, easing = FastOutSlowInEasing)); hop.animateTo(0f, spring(dampingRatio = 0.45f, stiffness = Spring.StiffnessMediumLow)) }
            // the logo pops up over them (a springy overshoot), then lights up: a glow swells and a shine sweeps across
            launch { delay(1850); logoIn.animateTo(1f, spring(dampingRatio = 0.5f, stiffness = Spring.StiffnessMediumLow)) }
            launch { delay(2250); light.animateTo(1f, tween(750, easing = FastOutSlowInEasing)) }
            launch { delay(2350); title.animateTo(1f, tween(600, easing = FastOutSlowInEasing)) }
        }
        delay(450)
        out.animateTo(0f, tween(300, easing = LinearEasing))
        finish()
    }
    Box(
        Modifier.fillMaxSize().graphicsLayer { alpha = out.value }.background(SplashNight)
            .clickable(remember { MutableInteractionSource() }, null) { finish() },
    ) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val wpx = constraints.maxWidth.toFloat(); val hpx = constraints.maxHeight.toFloat()
            Canvas(Modifier.fillMaxSize()) {
                val c = Offset(size.width / 2, size.height * 0.44f)
                drawCircle(Brush.radialGradient(listOf(Pink.copy(alpha = 0.28f * glow.value), Color.Transparent), Offset(size.width * 0.3f, c.y), size.width * 0.6f), size.width, Offset(size.width * 0.3f, c.y))
                drawCircle(Brush.radialGradient(listOf(Blue.copy(alpha = 0.28f * glow.value), Color.Transparent), Offset(size.width * 0.7f, c.y), size.width * 0.6f), size.width, Offset(size.width * 0.7f, c.y))
                // paw prints behind each of them, from the edges to where they are now
                val e = ease(walk.value)
                for (side in listOf(-1f, 1f)) {
                    val from = if (side < 0) -0.05f else 1.05f; val to = if (side < 0) 0.38f else 0.62f
                    val nowX = from + (to - from) * e
                    var k = 0
                    var x = from + (if (side < 0) 0.06f else -0.06f)
                    while ((side < 0 && x < nowX - 0.07f) || (side > 0 && x > nowX + 0.07f)) {
                        val y = c.y + size.width * 0.17f + (if (k % 2 == 0) -1 else 1) * size.width * 0.018f
                        val age = kotlin.math.abs(nowX - x)
                        paw(Offset(x * size.width, y), if (side < 0) 0f else 180f, size.width * 0.018f, (if (side < 0) Pink else Blue).copy(alpha = (0.85f - age * 1.2f).coerceIn(0.15f, 0.85f)))
                        x += if (side < 0) 0.07f else -0.07f; k++
                    }
                }
            }
            // the two of them, walking (8-frame loop), then standing and hopping together
            val frame = if (walk.value < 1f) (clock / 70) % 8 else 0
            val e = ease(walk.value)
            val pw = wpx * 0.27f; val ph = pw * 305f / 248f
            val a = art
            for ((side, frames) in listOf(-1f to (a?.girl ?: emptyList()), 1f to (a?.boy ?: emptyList()))) {
                if (frames.isEmpty()) continue
                val img = frames[frame] ?: continue
                val cxF = if (side < 0) -0.05f + (0.38f + 0.05f) * e else 1.05f - (1.05f - 0.62f) * e
                val bob = if (walk.value < 1f) kotlin.math.abs(kotlin.math.sin(clock / 70.0 * Math.PI / 4)).toFloat() * ph * 0.03f else 0f
                Image(img, null, Modifier
                    .offset { androidx.compose.ui.unit.IntOffset((cxF * wpx - pw / 2).toInt(), (hpx * 0.44f - ph * 0.62f - bob - hop.value * ph * 0.18f).toInt()) }
                    .size(with(androidx.compose.ui.platform.LocalDensity.current) { pw.toDp() }, with(androidx.compose.ui.platform.LocalDensity.current) { ph.toDp() }))
            }
        }
        // the logo, above the two of them
        art?.logo?.let { logo ->
            // pops up dim, then lights up: brightens to full, its glow swells, and a shine runs across it
            val l = light.value
            Box(Modifier.align(Alignment.TopCenter).padding(top = 64.dp).width(250.dp).aspectRatio(logo.width.toFloat() / logo.height).graphicsLayer {
                val k = logoIn.value; scaleX = 0.2f + 0.8f * k; scaleY = 0.2f + 0.8f * k; alpha = k.coerceIn(0f, 1f); translationY = (1 - k) * 40.dp.toPx()
            }, contentAlignment = Alignment.Center) {
                Canvas(Modifier.fillMaxSize().graphicsLayer { scaleX = 1.5f; scaleY = 1.5f }) {
                    val g = kotlin.math.sin(l * Math.PI).toFloat() * 0.5f + l * 0.3f
                    drawCircle(Brush.radialGradient(listOf(Blue.copy(alpha = 0.45f * g), Pink.copy(alpha = 0.2f * g), Color.Transparent)), size.minDimension / 2)
                }
                val b = 0.42f + 0.58f * l
                Box(Modifier.fillMaxSize().graphicsLayer { compositingStrategy = androidx.compose.ui.graphics.CompositingStrategy.Offscreen }) {
                    Image(logo, null, Modifier.fillMaxSize(), colorFilter = androidx.compose.ui.graphics.ColorFilter.colorMatrix(
                        androidx.compose.ui.graphics.ColorMatrix(floatArrayOf(b, 0f, 0f, 0f, 0f, 0f, b, 0f, 0f, 0f, 0f, 0f, b, 0f, 0f, 0f, 0f, 0f, 1f, 0f))))
                    Canvas(Modifier.fillMaxSize()) {                                   // the shine, only where the logo is
                        if (l > 0f && l < 1f) {
                            val x = -size.width * 0.5f + size.width * 2f * l
                            drawRect(Brush.linearGradient(listOf(Color.Transparent, Color.White.copy(alpha = 0.6f), Color.Transparent),
                                Offset(x - size.width * 0.18f, 0f), Offset(x + size.width * 0.18f, size.height * 0.5f)), blendMode = androidx.compose.ui.graphics.BlendMode.SrcAtop)
                        }
                    }
                }
            }
        }
        Column(Modifier.align(Alignment.Center).padding(top = 230.dp).graphicsLayer { alpha = title.value; translationY = (1 - title.value) * 14.dp.toPx() },
            horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Follow Poppy", color = Color.White, fontSize = 36.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.8).sp)
            Spacer(Modifier.height(6.dp))
            Text(w.t("פופי תוביל אותך לשם", "Poppy will lead the way"), color = Color.White.copy(alpha = 0.62f), fontSize = 16.sp)
        }
    }
}

private fun ease(t: Float): Float { val x = t.coerceIn(0f, 1f); return 1 - (1 - x) * (1 - x) }          // a steady walk that slows to a stop

private fun DrawScope.paw(c: Offset, angle: Float, s: Float, color: Color) {
    rotate(angle + 90f, c) {
        drawOval(color, Offset(c.x - s * 0.55f, c.y - s * 0.2f), Size(s * 1.1f, s * 0.85f))
        for ((dx, dy) in listOf(-0.5f to -0.55f, 0f to -0.8f, 0.5f to -0.55f)) drawCircle(color, s * 0.24f, Offset(c.x + dx * s, c.y + dy * s))
    }
}

/**
 * Who walks with you today? The two Poppys side by side on glass cards; a tap picks one (it springs) and goes on.
 * The last choice is marked.
 */
@Composable
internal fun ChoosePoppy(w: Words, last: String?, onPick: (String) -> Unit) {
    val context = LocalContext.current
    val imgs by androidx.compose.runtime.produceState<Map<String, ImageBitmap?>>(emptyMap()) {
        value = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) { mapOf("girl" to context.png("splash_poppy_girl.png"), "boy" to context.png("splash_poppy_boy.png")) }
    }
    val enter = remember { Animatable(0f) }
    var picked by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) { enter.animateTo(1f, spring(dampingRatio = 0.8f, stiffness = Spring.StiffnessLow)) }
    LaunchedEffect(picked) { val p = picked ?: return@LaunchedEffect; delay(260); onPick(p) }
    Box(Modifier.fillMaxSize().background(SplashNight)) {
        Canvas(Modifier.fillMaxSize()) {
            drawCircle(Brush.radialGradient(listOf(Pink.copy(alpha = 0.22f), Color.Transparent), Offset(size.width * 0.25f, size.height * 0.5f), size.width * 0.7f), size.width, Offset(size.width * 0.25f, size.height * 0.5f))
            drawCircle(Brush.radialGradient(listOf(Blue.copy(alpha = 0.22f), Color.Transparent), Offset(size.width * 0.75f, size.height * 0.5f), size.width * 0.7f), size.width, Offset(size.width * 0.75f, size.height * 0.5f))
        }
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(horizontal = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
            Text(w.t("מי ילווה אותך היום?", "Who's walking with you today?"), color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center, letterSpacing = (-0.4).sp, modifier = Modifier.graphicsLayer { alpha = enter.value })
            Spacer(Modifier.height(8.dp))
            Text(w.t("בחר בן או בת", "Pick a boy or a girl"), color = Color.White.copy(alpha = 0.6f), fontSize = 16.sp, modifier = Modifier.graphicsLayer { alpha = enter.value })
            Spacer(Modifier.height(28.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                for ((i, g) in listOf("girl", "boy").withIndex()) {
                    val accent = if (g == "boy") Blue else Pink
                    val src = remember { MutableInteractionSource() }
                    val pressed by src.collectIsPressedAsState()
                    val press = remember { Animatable(1f) }
                    LaunchedEffect(pressed, picked) { press.animateTo(if (picked == g) 1.06f else if (pressed) 0.95f else 1f, spring(dampingRatio = 0.55f, stiffness = Spring.StiffnessMedium)) }
                    val shape = RoundedCornerShape(28.dp)
                    Column(
                        Modifier.weight(1f).graphicsLayer {
                            scaleX = press.value; scaleY = press.value
                            val k = (enter.value * 1.2f - i * 0.2f).coerceIn(0f, 1f); alpha = k; translationY = (1 - k) * 40.dp.toPx()
                        }.clip(shape).background(Brush.verticalGradient(listOf(accent.copy(alpha = 0.30f), Color(0xCC111A2C))))
                            .border(if (last == g || picked == g) 2.dp else 1.dp, if (last == g || picked == g) accent else Color.White.copy(alpha = 0.18f), shape)
                            .clickable(src, null) { if (picked == null) picked = g }.padding(vertical = 18.dp, horizontal = 12.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        val img = imgs[g]
                        Box(Modifier.fillMaxWidth().aspectRatio(0.8f), contentAlignment = Alignment.Center) {
                            if (img != null) Image(img, null, Modifier.fillMaxSize()) else Canvas(Modifier.size(80.dp)) { miniPoppyIcon(accent) }
                        }
                        Spacer(Modifier.height(12.dp))
                        Text(if (g == "boy") w.t("בן", "Boy") else w.t("בת", "Girl"), color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}
