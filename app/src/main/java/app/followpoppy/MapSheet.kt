package app.followpoppy

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.SystemClock
import android.util.Log
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.net.URL
import kotlin.math.PI
import kotlin.math.atan
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.tan

/**
 * Where a map point lands on a Mapbox static image: Web Mercator (512 px tiles) around [center] at [zoom], the map turned
 * so that [bearing] (degrees, clockwise from north) points up. Returns logical pixels from the image's top-left.
 */
internal object StaticMapProjection {
    private fun size(zoom: Double) = 512.0 * Math.pow(2.0, zoom)
    private fun world(p: LatLng, zoom: Double): DoubleArray {
        val s = size(zoom); val lat = Math.toRadians(p.lat.coerceIn(-85.0, 85.0))
        return doubleArrayOf((p.lng + 180) / 360 * s, (1 - ln(tan(lat) + 1 / cos(lat)) / PI) / 2 * s)
    }
    fun project(p: LatLng, center: LatLng, zoom: Double, bearing: Double, w: Double, h: Double): DoubleArray {
        val a = world(p, zoom); val c = world(center, zoom)
        val dx = a[0] - c[0]; val dy = a[1] - c[1]; val b = Math.toRadians(bearing)
        return doubleArrayOf(w / 2 + dx * cos(b) + dy * sin(b), h / 2 - dx * sin(b) + dy * cos(b))
    }
    /** The map point at image pixel ([x], [y]): the inverse of [project]. */
    fun unproject(x: Double, y: Double, center: LatLng, zoom: Double, bearing: Double, w: Double, h: Double): LatLng {
        val b = Math.toRadians(bearing); val X = x - w / 2; val Y = y - h / 2
        val dx = X * cos(b) - Y * sin(b); val dy = X * sin(b) + Y * cos(b)
        val c = world(center, zoom); val s = size(zoom)
        val wx = c[0] + dx; val wy = c[1] + dy
        return LatLng(Math.toDegrees(atan(kotlin.math.sinh(PI * (1 - 2 * wy / s)))), wx / s * 360 - 180)
    }
    /** Logical pixels per metre at [lat] and [zoom]. */
    fun pxPerMetre(lat: Double, zoom: Double) = size(zoom) / (40_075_016.7 * cos(Math.toRadians(lat)))
}

/** A fetched map image and the view it shows (logical size [w] x [h]). */
private class MapImage(val bm: Bitmap, val center: LatLng, val zoom: Double, val bearing: Double, val w: Int, val h: Int)

/**
 * The route on a street map you can pinch to zoom out or in and drag around (one finger), like a phone's maps app.
 * It follows you, turned the way you face, until you move it; then a "back to me" button returns to following.
 * Shows the route as Poppy's paw prints (a line when zoomed far out; the walked part faded), Poppy, you, the
 * destination flag and a scale bar. The image is a Mapbox static map; a new one is fetched when the view has moved.
 */
@Composable
internal fun RouteMap(w: Words, api: MapboxApi, route: Route?, along: Double, poppyAlong: Double, at: () -> LatLng?, heading: () -> Double,
                      gender: String, modifier: Modifier = Modifier, startZoom: Double = 16.4, bottomInset: Float = 0f) {
    val dens = LocalDensity.current.density
    var box by remember { mutableStateOf(IntSize.Zero) }
    var img by remember { mutableStateOf<MapImage?>(null) }
    var zoom by remember { mutableDoubleStateOf(startZoom) }
    var free by remember { mutableStateOf<LatLng?>(null) }            // null = following you; else the centre you dragged to
    var freeBearing by remember { mutableDoubleStateOf(0.0) }
    var gestureAt by remember { mutableLongStateOf(0L) }
    var frame by remember { mutableLongStateOf(0L) }                     // redraws a few times a second (you and Poppy move)
    val tint = if (gender == "boy") Color(0xFF5FB3FF) else Color(0xFFFF7FBF)
    LaunchedEffect(Unit) { while (true) { delay(150); frame++ } }
    LaunchedEffect(box) {
        if (box.width == 0) return@LaunchedEffect
        val bw = box.width / dens; val bh = box.height / dens
        // the image is at most 640 x 640 (logical); a bigger view gets a lower zoom image, drawn enlarged
        val k = max(1.0, max(bw / 640.0, bh / 640.0))
        val wl = (bw / k).roundToInt().coerceIn(120, 640); val hl = (bh / k).roundToInt().coerceIn(120, 640)
        var lastFetch = 0L
        while (true) {
            delay(250)
            val now = SystemClock.uptimeMillis()
            if (now - gestureAt < 350 || now - lastFetch < 1200) continue
            val c = free ?: at() ?: continue
            val b = if (free != null) freeBearing else heading().let { if (it.isNaN()) 0.0 else it }
            val z = zoom - ln(k) / ln(2.0)
            val cur = img
            val need = cur == null || kotlin.math.abs(cur.zoom - z) > 0.15 ||
                Geo.distance(cur.center, c) * StaticMapProjection.pxPerMetre(c.lat, cur.zoom) > minOf(wl, hl) * 0.18 ||
                (free == null && (kotlin.math.abs(GeoAlign.wrap(Math.toRadians(b - cur.bearing))) > Math.toRadians(25.0) || now - lastFetch > 10_000))
            if (!need) continue
            lastFetch = now
            runCatching { withContext(Dispatchers.IO) { URL(api.staticMapUrl(null, c, z, b, wl, hl)).openStream().use { BitmapFactory.decodeStream(it) } } }
                .onSuccess { bm -> if (bm != null) img = MapImage(bm, c, z, b, wl, hl) }
                .onFailure { Log.w("FollowPoppy", "map: ${it.message}") }
        }
    }
    Box(modifier.onSizeChanged { box = it }) {
        Canvas(Modifier.fillMaxSize().pointerInput(Unit) {
            detectTransformGestures { _, pan, gz, _ ->
                val im = img ?: return@detectTransformGestures
                gestureAt = SystemClock.uptimeMillis()
                val bw = size.width / dens; val bh = size.height / dens
                val k = max(1.0, max(bw / 640.0, bh / 640.0))
                val scale = Math.pow(2.0, zoom - ln(k) / ln(2.0) - im.zoom)
                // where the view's centre is now, in the image, moved by the drag
                val c0 = free ?: at() ?: im.center
                val q = StaticMapProjection.project(c0, im.center, im.zoom, im.bearing, im.w.toDouble(), im.h.toDouble())
                val nq = doubleArrayOf(q[0] - pan.x / dens / scale, q[1] - pan.y / dens / scale)
                if (free == null) freeBearing = im.bearing
                if (pan.getDistance() > 0.5f || free != null) free = StaticMapProjection.unproject(nq[0], nq[1], im.center, im.zoom, im.bearing, im.w.toDouble(), im.h.toDouble())
                zoom = (zoom + ln(gz.toDouble()) / ln(2.0)).coerceIn(12.0, 19.0)
            }
        }) {
            frame.let { }                                                          // read: redraw as you move
            val im = img ?: return@Canvas
            val bw = size.width / dens; val bh = size.height / dens
            val k = max(1.0, max(bw / 640.0, bh / 640.0))
            val scale = Math.pow(2.0, zoom - ln(k) / ln(2.0) - im.zoom)
            val vc = free ?: at() ?: im.center
            val qv = StaticMapProjection.project(vc, im.center, im.zoom, im.bearing, im.w.toDouble(), im.h.toDouble())
            val cx = size.width / 2; val cy = (size.height - bottomInset) / 2
            fun sc(q: DoubleArray) = Offset((cx + (q[0] - qv[0]) * scale * dens).toFloat(), (cy + (q[1] - qv[1]) * scale * dens).toFloat())
            fun px(p: LatLng) = sc(StaticMapProjection.project(p, im.center, im.zoom, im.bearing, im.w.toDouble(), im.h.toDouble()))
            val tl = sc(doubleArrayOf(0.0, 0.0)); val br = sc(doubleArrayOf(im.w.toDouble(), im.h.toDouble()))
            drawImage(im.bm.asImageBitmap(), dstOffset = IntOffset(tl.x.roundToInt(), tl.y.roundToInt()),
                dstSize = IntSize((br.x - tl.x).roundToInt().coerceAtLeast(1), (br.y - tl.y).roundToInt().coerceAtLeast(1)))
            val metrePx = (StaticMapProjection.pxPerMetre(vc.lat, im.zoom) * scale * dens).toFloat()
            val r = route
            if (r != null) {
                fun g(s: Double) = Geo.fromEnu(r.line.origin, r.line.at(s))
                // the route: a soft glowing line, and Poppy's paw prints on it when close enough to see them
                val stepLine = (6.0 / metrePx).coerceIn(1.0, 40.0)
                fun pathOf(s0: Double, s1: Double) = Path().apply { var s = s0; var first = true; while (s <= s1 + 1e-6) { val p = px(g(s.coerceAtMost(s1))); if (first) moveTo(p.x, p.y) else lineTo(p.x, p.y); first = false; if (s >= s1) break; s = (s + stepLine).coerceAtMost(s1) } }
                val done = along.coerceIn(0.0, r.length)
                val lw = (metrePx * 3.2f).coerceIn(6f, 20f)
                if (done > 0.5) drawPath(pathOf(0.0, done), tint.copy(alpha = 0.35f), style = Stroke(lw, cap = StrokeCap.Round, join = StrokeJoin.Round))
                val ahead = pathOf(done, r.length)
                drawPath(ahead, tint.copy(alpha = 0.28f), style = Stroke(lw * 2.2f, cap = StrokeCap.Round, join = StrokeJoin.Round))
                drawPath(ahead, tint, style = Stroke(lw, cap = StrokeCap.Round, join = StrokeJoin.Round))
                if (metrePx > 1.6f) {
                    val step = (26f / metrePx).toDouble().coerceAtLeast(3.0); var kk = 0; var s = done
                    while (s <= r.length) {
                        val pa = px(g(s)); val pb = px(g(s + 1.0))
                        if (pa.x > -20 && pa.y > -20 && pa.x < size.width + 20 && pa.y < size.height + 20) {
                            val ang = atan2((pb.y - pa.y).toDouble(), (pb.x - pa.x).toDouble()).toFloat()
                            val side = if (kk % 2 == 0) 1f else -1f
                            paw(pa + Offset(-sin(ang) * side * lw * 0.22f, cos(ang) * side * lw * 0.22f), ang, lw * 0.16f, Color.White.copy(alpha = 0.92f))
                        }
                        s += step; kk++
                    }
                }
                // destination flag
                val d = px(g(r.length))
                drawLine(Color.White, d, d + Offset(0f, -34f), 4f)
                drawPath(Path().apply { moveTo(d.x, d.y - 34f); lineTo(d.x + 26f, d.y - 27f); lineTo(d.x, d.y - 19f); close() }, Color(0xFFF5B841))
                drawCircle(Color(0xFFF5B841), 6f, d)
                if (!poppyAlong.isNaN()) miniPoppy(px(g(poppyAlong)), tint, 1f)
            }
            // you: an arrow the way you face (up while following, turned when you moved the map)
            at()?.let { p ->
                val me = px(p)
                val rot = if (free == null) 0f else (heading().let { if (it.isNaN()) im.bearing else it } - im.bearing).toFloat()
                drawCircle(Color(0x4022D3EE), 30f, me)
                rotate(rot, me) {
                    drawPath(Path().apply { moveTo(me.x, me.y - 18f); lineTo(me.x + 13f, me.y + 13f); lineTo(me.x, me.y + 6f); lineTo(me.x - 13f, me.y + 13f); close() }, Color.White)
                    drawPath(Path().apply { moveTo(me.x, me.y - 13f); lineTo(me.x + 9f, me.y + 9f); lineTo(me.x, me.y + 4f); lineTo(me.x - 9f, me.y + 9f); close() }, Color(0xFF22D3EE))
                }
            }
            scaleBar(metrePx, dens, bottomInset)
        }
        if (img == null) Text(w.t("טוען מפה…", "Loading the map…"), color = Color(0xFF9FB0C8), fontSize = 14.sp, modifier = Modifier.align(Alignment.Center))
        // back to following you
        if (free != null) Box(Modifier.align(Alignment.TopEnd).padding(top = 14.dp, end = 14.dp).size(44.dp).clip(CircleShape)
            .background(Color(0xE60B1220)).border(1.dp, Color(0x55FFFFFF), CircleShape).clickable { free = null; zoom = startZoom }, contentAlignment = Alignment.Center) {
            Canvas(Modifier.size(20.dp)) {                                     // a location arrow
                val s = size.width
                drawPath(Path().apply { moveTo(s * 0.9f, s * 0.1f); lineTo(s * 0.55f, s * 0.92f); lineTo(s * 0.45f, s * 0.55f); lineTo(s * 0.08f, s * 0.45f); close() }, Color(0xFF22D3EE))
            }
        }
    }
}

/** A short scale bar (bottom-left): a round number of metres and its length. */
private fun DrawScope.scaleBar(metrePx: Float, dens: Float, bottomInset: Float) {
    if (metrePx <= 0f) return
    val want = 90 * dens / metrePx
    val nice = listOf(10, 20, 50, 100, 200, 500, 1000, 2000, 5000).lastOrNull { it <= want } ?: 10
    val len = nice * metrePx; val x = 16 * dens; val y = size.height - bottomInset - 18 * dens
    drawLine(Color(0x99000000), Offset(x, y), Offset(x + len, y), 7f, StrokeCap.Round)
    drawLine(Color.White, Offset(x, y), Offset(x + len, y), 3.5f, StrokeCap.Round)
    val label = if (nice >= 1000) "${nice / 1000} km" else "$nice m"
    drawContext.canvas.nativeCanvas.drawText(label, x, y - 8 * dens, android.graphics.Paint().apply {
        color = android.graphics.Color.WHITE; textSize = 12 * dens; isAntiAlias = true; setShadowLayer(4f, 0f, 1f, android.graphics.Color.BLACK)
    })
}

/**
 * The map that slides up from the bottom with a tap: a frosted-glass dome (a window onto the map) with the map filling
 * it edge to edge; pinch and drag it like a maps app. Drag the handle down (or tap Close) to close.
 */
@Composable
internal fun MapSheet(w: Words, api: MapboxApi, route: Route?, along: Double, poppyAlong: Double, at: () -> LatLng?, heading: () -> Double,
                      gender: String, remaining: String, onClose: () -> Unit) {
    var drag by remember { mutableFloatStateOf(0f) }
    val shape: Shape = DomeShape(0.42f, 30.dp)
    Box(
        Modifier.fillMaxWidth().padding(horizontal = 10.dp).height(470.dp).graphicsLayer { translationY = drag }
            .shadow(28.dp, shape).clip(shape).background(Color(0xFF0B1220))
    ) {
        RouteMap(w, api, route, along, poppyAlong, at, heading, gender, Modifier.fillMaxSize(), bottomInset = 0f)
        // the glass rim and a soft shade under the top edge, so the dome reads as a window
        Box(Modifier.fillMaxSize().border(1.5.dp, Brush.verticalGradient(listOf(Color(0xCCFFFFFF), Color(0x33FFFFFF), Color(0x14FFFFFF))), shape))
        // the handle: drag it down to close
        Box(Modifier.align(Alignment.TopCenter).padding(top = 10.dp).width(120.dp).height(36.dp)
            .pointerInput(Unit) { detectVerticalDragGestures(onDragEnd = { if (drag > 120f) onClose(); drag = 0f }, onDragCancel = { drag = 0f }) { _, dy -> drag = (drag + dy).coerceAtLeast(0f) } }
            .clickable { onClose() }, contentAlignment = Alignment.TopCenter) {
            Box(Modifier.padding(top = 4.dp).width(44.dp).height(5.dp).clip(RoundedCornerShape(3.dp)).background(Color(0xCCFFFFFF)))
        }
        Row(Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(12.dp).clip(RoundedCornerShape(20.dp))
            .background(Color(0xD90B1220)).border(1.dp, Color(0x33FFFFFF), RoundedCornerShape(20.dp)).padding(start = 16.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Text(remaining, color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            Spacer(Modifier.width(8.dp))
            Text(w.t("סגירה", "Close"), color = Color(0xFF0B1220), fontSize = 14.sp, fontWeight = FontWeight.ExtraBold,
                modifier = Modifier.clip(RoundedCornerShape(14.dp)).background(Color.White).clickable { onClose() }.padding(horizontal = 16.dp, vertical = 8.dp))
        }
    }
}

/** One paw print: a pad and three toes, pointing along [angle] (radians, screen). */
private fun DrawScope.paw(c: Offset, angle: Float, s: Float, color: Color) {
    rotate(degrees = Math.toDegrees(angle.toDouble()).toFloat() + 90f, pivot = c) {
        drawOval(color, Offset(c.x - s * 1.15f, c.y - s * 0.5f), Size(s * 2.3f, s * 1.9f))
        for ((dx, dy) in listOf(-1.25f to -1.35f, 0f to -1.85f, 1.25f to -1.35f)) drawCircle(color, s * 0.55f, Offset(c.x + dx * s, c.y + dy * s))
    }
}

/** A tiny Poppy for the map: a fluffy ball with two long ears and two eyes, outlined in white. */
private fun DrawScope.miniPoppy(c: Offset, tint: Color, k: Float) {
    val r = 15f * k
    for (sx in listOf(-1f, 1f)) {
        drawOval(Color.White, Offset(c.x + sx * r * 0.42f - r * 0.32f, c.y - r * 2.05f), Size(r * 0.64f, r * 1.5f))
        drawOval(tint, Offset(c.x + sx * r * 0.42f - r * 0.24f, c.y - r * 1.97f), Size(r * 0.48f, r * 1.34f))
    }
    drawCircle(Color.White, r + 3f, c); drawCircle(tint, r, c)
    for (sx in listOf(-1f, 1f)) { drawCircle(Color(0xFF1C1622), r * 0.2f, Offset(c.x + sx * r * 0.36f, c.y - r * 0.05f)); drawCircle(Color.White, r * 0.07f, Offset(c.x + sx * r * 0.36f + 1.5f, c.y - r * 0.12f)) }
    drawCircle(Color(0x66FF7BA8), r * 0.14f, Offset(c.x - r * 0.62f, c.y + r * 0.25f)); drawCircle(Color(0x66FF7BA8), r * 0.14f, Offset(c.x + r * 0.62f, c.y + r * 0.25f))
    drawArc(Color(0xFF2A1A24), 20f, 140f, false, Offset(c.x - r * 0.22f, c.y + r * 0.1f), Size(r * 0.44f, r * 0.3f), style = Stroke(width = 2.5f))
}
