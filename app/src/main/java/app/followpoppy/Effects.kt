package app.followpoppy

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/**
 * The little effects around Poppy, as on the character sheet: speed lines when she runs, a "?" when she thinks,
 * hearts when she hugs the pin, yellow bursts when she cheers, blue ticks by a thumbs-up / ok / peek, a soft glow
 * over the meditation ring. [hx], [hy]: just above her head (dp); [size]: her height on screen (dp).
 */
@Composable
internal fun PoppyEffects(act: PoppyGuide.Act, running: Boolean, hx: Float, hy: Float, size: Float, gender: String) {
    if (act == PoppyGuide.Act.NONE && !running) return
    val t by rememberInfiniteTransition(label = "fx").animateFloat(0f, 1f, infiniteRepeatable(tween(1200, easing = LinearEasing), RepeatMode.Restart), label = "t")
    val blue = Color(0xFF3B9BFF); val yellow = Color(0xFFFFC21A); val theme = if (gender == "girl") Color(0xFFFF4F9A) else blue
    Canvas(Modifier.fillMaxSize()) {
        val d = density
        val cx = hx * d; val top = hy * d; val s = size * d                      // s: her height in px
        val mid = top + s * 0.55f
        val w = (s * 0.012f).coerceIn(2.5f, 9f)
        when {
            act == PoppyGuide.Act.THINK -> question(Offset(cx + s * 0.32f, top + s * 0.02f - s * 0.05f * sin(t * 2 * PI).toFloat()), s * 0.22f, blue, w * 1.4f)
            act == PoppyGuide.Act.PIN -> {
                for (k in 0 until 3) {
                    val ph = (t + k / 3f) % 1f
                    heart(Offset(cx + s * (0.25f + 0.08f * k), top + s * (0.15f - 0.35f * ph)), s * (0.07f + 0.02f * k), theme.copy(alpha = 1f - ph))
                }
            }
            act == PoppyGuide.Act.CHEER -> {
                val pulse = 0.85f + 0.15f * sin(t * 4 * PI).toFloat()
                for (side in listOf(-1f, 1f)) for ((ang, len) in listOf(-35f to 0.16f, 0f to 0.2f, 35f to 0.16f)) {
                    val a = Math.toRadians((if (side < 0) 180.0 - ang else ang.toDouble())).toFloat()
                    val r0 = s * 0.38f; val r1 = r0 + s * len * pulse
                    val c0 = Offset(cx + cos(a) * r0, top + s * 0.2f - sin(a) * r0 * 0.8f); val c1 = Offset(cx + cos(a) * r1, top + s * 0.2f - sin(a) * r1 * 0.8f)
                    drawLine(yellow, c0, c1, w * 1.8f, StrokeCap.Round)
                }
            }
            act == PoppyGuide.Act.THUMBS || act == PoppyGuide.Act.OK || act == PoppyGuide.Act.PEEK || act == PoppyGuide.Act.PHONE -> {
                val side = if (act == PoppyGuide.Act.PEEK || act == PoppyGuide.Act.OK) 1f else -1f
                val base = Offset(cx + side * s * 0.36f, top + s * 0.28f)
                val k = 0.9f + 0.1f * sin(t * 4 * PI).toFloat()
                for ((ang, len) in listOf(120f to 0.1f, 155f to 0.12f, 190f to 0.09f)) {
                    val a = Math.toRadians(if (side > 0) (180.0 - ang) else ang.toDouble()).toFloat()
                    val p0 = base + Offset(cos(a) * s * 0.04f, -sin(a) * s * 0.04f); val p1 = base + Offset(cos(a) * s * (0.04f + len * k), -sin(a) * s * (0.04f + len * k))
                    drawLine(blue, p0, p1, w * 1.6f, StrokeCap.Round)
                }
            }
            act == PoppyGuide.Act.MEDITATE -> {
                val g = 0.35f + 0.25f * sin(t * 2 * PI).toFloat()
                drawCircle(Color(0xFF4FD8FF).copy(alpha = g * 0.35f), s * 0.55f, Offset(cx, top + s * 1.0f))
            }
        }
        // speed lines behind her when she runs
        if (running && act == PoppyGuide.Act.NONE) {
            for (k in 0 until 3) {
                val ph = (t * 2 + k / 3f) % 1f
                val y = mid + s * (k - 1) * 0.14f
                val x0 = cx - s * (0.35f + 0.25f * ph); val x1 = x0 - s * 0.22f
                drawLine(Color(0xFF7FD8FF).copy(alpha = 0.8f * (1 - ph)), Offset(x0, y), Offset(x1, y), w * 1.4f, StrokeCap.Round)
                drawLine(Color(0xFF7FD8FF).copy(alpha = 0.8f * (1 - ph)), Offset(-x0 + 2 * cx, y), Offset(-x1 + 2 * cx, y), w * 1.4f, StrokeCap.Round)
            }
        }
    }
}

private fun DrawScope.question(c: Offset, h: Float, color: Color, w: Float) {
    val p = Path().apply {
        moveTo(c.x - h * 0.28f, c.y - h * 0.18f)
        cubicTo(c.x - h * 0.28f, c.y - h * 0.62f, c.x + h * 0.32f, c.y - h * 0.62f, c.x + h * 0.32f, c.y - h * 0.22f)
        cubicTo(c.x + h * 0.32f, c.y + h * 0.02f, c.x, c.y + h * 0.02f, c.x, c.y + h * 0.22f)
    }
    drawPath(p, color, style = Stroke(w, cap = StrokeCap.Round))
    drawCircle(color, w * 0.75f, Offset(c.x, c.y + h * 0.42f))
}

private fun DrawScope.heart(c: Offset, r: Float, color: Color) {
    val p = Path().apply {
        moveTo(c.x, c.y + r * 0.9f)
        cubicTo(c.x - r * 1.3f, c.y + r * 0.1f, c.x - r * 0.9f, c.y - r * 0.9f, c.x, c.y - r * 0.35f)
        cubicTo(c.x + r * 0.9f, c.y - r * 0.9f, c.x + r * 1.3f, c.y + r * 0.1f, c.x, c.y + r * 0.9f)
        close()
    }
    drawPath(p, color)
}
